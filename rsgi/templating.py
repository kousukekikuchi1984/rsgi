from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence, Tuple

from .response import Response

try:
    from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound, select_autoescape
except ModuleNotFoundError as exc:  # pragma: no cover - exercised via fallback error paths
    Environment = FileSystemLoader = Template = TemplateNotFound = select_autoescape = None  # type: ignore
    _JINJA_IMPORT_ERROR = exc
else:
    _JINJA_IMPORT_ERROR = None

_DEFAULT_MEDIA_TYPE = "text/html; charset=utf-8"


def _require_jinja() -> None:
    if _JINJA_IMPORT_ERROR is not None:  # pragma: no cover - depends on environment
        raise ModuleNotFoundError(
            "Template support requires 'jinja2'. Install it via `uv add jinja2` or `pip install jinja2`."
        ) from _JINJA_IMPORT_ERROR

def _ensure_content_type(headers: Sequence[Tuple[str, str]] | None, media_type: str) -> list[Tuple[str, str]]:
    prepared: list[Tuple[str, str]] = list(headers or [])
    lowered = media_type.lower()
    for idx, (name, value) in enumerate(prepared):
        if name.lower() == "content-type":
            prepared[idx] = (name, media_type)
            break
    else:
        prepared.append(("content-type", media_type))
    return prepared


class TemplateEngine:
    """
    Thin wrapper around a Jinja2 Environment that renders templates by name.
    """

    def __init__(self, env: Environment):
        self._env = env

    @classmethod
    def from_directory(
        cls,
        directory: str | Path,
        *,
        autoescape: tuple[str, ...] = ("html", "xml"),
        enable_async: bool = False,
        **env_options: Any,
    ) -> "TemplateEngine":
        _require_jinja()
        loader = FileSystemLoader(str(directory))
        options: dict[str, Any] = {
            "loader": loader,
            "autoescape": select_autoescape(autoescape),
            "enable_async": enable_async,
        }
        options.update(env_options)
        env = Environment(**options)
        return cls(env)

    def render(self, template_name: str, context: Mapping[str, Any]) -> str:
        template = self._get_template(template_name)
        if self._env.is_async:
            raise RuntimeError("TemplateEngine is configured for async rendering; call render_async instead.")
        return template.render(**context)

    async def render_async(self, template_name: str, context: Mapping[str, Any]) -> str:
        template = self._get_template(template_name)
        if not self._env.is_async:
            return template.render(**context)
        return await template.render_async(**context)

    def _get_template(self, template_name: str) -> Template:
        try:
            return self._env.get_template(template_name)
        except TemplateNotFound as exc:
            raise FileNotFoundError(f"Template '{template_name}' was not found.") from exc


class TemplateResponse(Response):
    """
    Render a named template using the provided TemplateEngine and wrap it as a Response.
    """

    def __init__(
        self,
        template_name: str,
        context: Mapping[str, Any] | None,
        *,
        engine: TemplateEngine,
        status: int = 200,
        headers: Sequence[Tuple[str, str]] | None = None,
        media_type: str = _DEFAULT_MEDIA_TYPE,
        use_async: bool | None = None,
    ):
        ctx = dict(context or {})
        if use_async is None:
            use_async = engine._env.is_async  # type: ignore[attr-defined]
        if use_async:
            raise RuntimeError("Async template rendering is not supported in TemplateResponse yet.")
        rendered = engine.render(template_name, ctx)
        prepared_headers = _ensure_content_type(headers, media_type)
        super().__init__(status, prepared_headers, rendered.encode("utf-8"))
