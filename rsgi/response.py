from __future__ import annotations

import json
from dataclasses import dataclass
from string import Template
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple


class TemplateRenderer(Protocol):
    def __call__(self, template: str, context: Mapping[str, Any]) -> str:
        ...


TemplateSource = str | Callable[[Mapping[str, Any]], str]


def _default_template_renderer(template: str, context: Mapping[str, Any]) -> str:
    return Template(template).safe_substitute(context)


def _ensure_content_type(headers: Sequence[Tuple[str, str]] | None, media_type: str) -> List[Tuple[str, str]]:
    prepared = list(headers or [])
    for idx, (key, value) in enumerate(prepared):
        if key.lower() == "content-type":
            prepared[idx] = (key, media_type)
            break
    else:
        prepared.append(("content-type", media_type))
    return prepared


def _encode_to_bytes(data: str | bytes) -> bytes:
    return data if isinstance(data, bytes) else data.encode("utf-8")


@dataclass(frozen=True)
class Response:
    status: int
    headers: List[Tuple[str, str]]
    body: bytes

    @staticmethod
    def text(
        body: str,
        status: int = 200,
        content_type: str = "text/plain; charset=utf-8",
    ) -> "Response":
        return Response(status, [("content-type", content_type)], body.encode("utf-8"))

    @staticmethod
    def json(
        obj: Any,
        status: int = 200,
        content_type: str = "application/json; charset=utf-8",
    ) -> "Response":
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return Response(status, [("content-type", content_type)], data)

    @staticmethod
    def html(body: str, status: int = 200, content_type: str = "text/html; charset=utf-8") -> "Response":
        return Response(status, [("content-type", content_type)], body.encode("utf-8"))

    @staticmethod
    def bytes(
        body: bytes,
        status: int = 200,
        content_type: str = "application/octet-stream",
    ) -> "Response":
        return Response(status, [("content-type", content_type)], body)

    @staticmethod
    def render(
        template: TemplateSource,
        context: Mapping[str, Any] | None = None,
        *,
        renderer: TemplateRenderer | None = None,
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
    ) -> "Response":
        ctx: Dict[str, Any] = dict(context or {})
        if callable(template) and not isinstance(template, str):
            html = template(ctx)
        else:
            engine = renderer or _default_template_renderer
            html = engine(str(template), ctx)
        return Response.html(html, status=status, content_type=content_type)


class BaseJSONResponse(Response):
    media_type = "application/json; charset=utf-8"

    def __init__(
        self,
        content: Any,
        *,
        status: int = 200,
        headers: Sequence[Tuple[str, str]] | None = None,
        **serialize_kwargs: Any,
    ):
        payload = self._render(content, **serialize_kwargs)
        prepared = _ensure_content_type(headers, self.media_type)
        super().__init__(status, prepared, payload)

    def _render(self, content: Any, **serialize_kwargs: Any) -> bytes:
        raise NotImplementedError


class JSONResponse(BaseJSONResponse):
    def _render(self, content: Any, **serialize_kwargs: Any) -> bytes:
        dumps_kwargs = serialize_kwargs.get("dumps_kwargs") or {}
        payload = json.dumps(
            content,
            ensure_ascii=False,
            separators=(",", ":"),
            **dumps_kwargs,
        )
        return _encode_to_bytes(payload)


try:  # pragma: no cover - optional dependency
    import ujson as _ujson
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    _ujson = None  # type: ignore


class UJSONResponse(BaseJSONResponse):
    def _render(self, content: Any, **serialize_kwargs: Any) -> bytes:
        if _ujson is None:  # pragma: no cover - environment specific
            raise ModuleNotFoundError(
                "UJSONResponse requires 'ujson'. Install it via `uv add ujson` or `pip install ujson`."
            )
        dumps_kwargs = serialize_kwargs.get("dumps_kwargs") or {}
        payload = _ujson.dumps(content, **dumps_kwargs)
        return _encode_to_bytes(payload)


try:  # pragma: no cover - optional dependency
    import orjson as _orjson
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    _orjson = None  # type: ignore


class ORJSONResponse(BaseJSONResponse):
    def _render(self, content: Any, **serialize_kwargs: Any) -> bytes:
        if _orjson is None:  # pragma: no cover - environment specific
            raise ModuleNotFoundError(
                "ORJSONResponse requires 'orjson'. Install it via `uv add orjson` or `pip install orjson`."
            )
        kwargs: Dict[str, Any] = {}
        option = serialize_kwargs.get("option")
        default = serialize_kwargs.get("default")
        if option is not None:
            kwargs["option"] = option
        if default is not None:
            kwargs["default"] = default
        return _orjson.dumps(content, **kwargs)


try:  # pragma: no cover - optional dependency
    import msgpack as _msgpack
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    _msgpack = None  # type: ignore


class MsgPackResponse(BaseJSONResponse):
    media_type = "application/msgpack"

    def _render(self, content: Any, **serialize_kwargs: Any) -> bytes:
        if _msgpack is None:  # pragma: no cover - environment specific
            raise ModuleNotFoundError(
                "MsgPackResponse requires 'msgpack'. Install it via `uv add msgpack` or `pip install msgpack`."
            )
        pack_kwargs = serialize_kwargs.get("pack_kwargs") or {}
        return _msgpack.packb(content, **pack_kwargs)
