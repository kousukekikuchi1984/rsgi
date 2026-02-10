from __future__ import annotations

import json
from dataclasses import dataclass
from string import Template
from typing import Any, Callable, Dict, List, Mapping, Protocol, Tuple


class TemplateRenderer(Protocol):
    def __call__(self, template: str, context: Mapping[str, Any]) -> str:
        ...


TemplateSource = str | Callable[[Mapping[str, Any]], str]


def _default_template_renderer(template: str, context: Mapping[str, Any]) -> str:
    return Template(template).safe_substitute(context)


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
