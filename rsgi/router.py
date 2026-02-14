from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Pattern, Tuple, get_type_hints

from pydantic import BaseModel, ValidationError

from .request import Request
from .response import Response

Handler = Callable[..., Awaitable[Response]]

_PARAM_RE = re.compile(r"{([a-zA-Z_][a-zA-Z0-9_]*)}")
_UNSET = object()


@dataclass(frozen=True)
class _Route:
    method: str
    template: str
    regex: Pattern[str]
    param_names: List[str]
    handler: Handler


@dataclass(frozen=True)
class ParamInfo:
    source: str
    default: Any
    alias: str | None
    required: bool


@dataclass(frozen=True)
class DependencySpec:
    dependency: Callable[..., Any]
    use_cache: bool = True


def Query(default: Any = _UNSET, *, alias: str | None = None) -> ParamInfo:
    required = default is _UNSET
    actual_default = inspect._empty if required else default
    return ParamInfo("query", actual_default, alias, required)


def Path(default: Any = _UNSET, *, alias: str | None = None) -> ParamInfo:
    required = default is _UNSET
    actual_default = inspect._empty if required else default
    return ParamInfo("path", actual_default, alias, required)


def Depends(dependency: Callable[..., Any], *, use_cache: bool = True) -> DependencySpec:
    return DependencySpec(dependency=dependency, use_cache=use_cache)


def _compile_path(template: str) -> Tuple[Pattern[str], List[str]]:
    """
    "/users/{id}" -> r"^/users/(?P<id>[^/]+)$"
    """
    names: List[str] = []

    def repl(m: re.Match[str]) -> str:
        name = m.group(1)
        names.append(name)
        return fr"(?P<{name}>[^/]+)"

    pattern = "^" + _PARAM_RE.sub(repl, template) + "$"
    return re.compile(pattern), names


def _normalize_template(template: str) -> str:
    if not template:
        return "/"
    if not template.startswith("/"):
        template = "/" + template
    if template != "/" and template.endswith("/"):
        template = template[:-1]
    return template or "/"


def _normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    normalized = _normalize_template(prefix)
    return "" if normalized == "/" else normalized


def _join_paths(prefix: str, template: str) -> str:
    template = _normalize_template(template)
    if not prefix:
        return template
    if template == "/":
        return prefix
    if prefix == "/":
        return template
    return prefix.rstrip("/") + template


def _coerce(value: str, anno: Any) -> Any:
    """
    Minimal type coercion for path/query params.
    Extend later (UUID, enums, etc).
    """
    if anno is inspect._empty or anno is str or anno is Any:
        return value
    if anno is int:
        return int(value)
    if anno is float:
        return float(value)
    if anno is bool:
        # accept typical forms
        v = value.strip().lower()
        if v in ("1", "true", "t", "yes", "y", "on"):
            return True
        if v in ("0", "false", "f", "no", "n", "off"):
            return False
        raise ValueError(f"Invalid bool: {value!r}")
    # fallback: leave as string
    return value


class _ParamValidationError(Exception):
    def __init__(self, error: str, param: str, value: Any = None, *, status: int = 400):
        self.response = Response.json(
            {
                "error": error,
                "param": param,
                "value": value,
            },
            status=status,
        )
        super().__init__(error)


class _ResolverContext:
    def __init__(self, request: Request, raw_path_params: Dict[str, str]):
        self.request = request
        self.raw_path_params = raw_path_params
        self.query_params = request.query_params
        self._dependency_cache: Dict[DependencySpec, Any] = {}
        self._model_payload: Dict[str, Any] | None = None

    async def resolve_dependency(self, spec: DependencySpec) -> Any:
        if spec.use_cache and spec in self._dependency_cache:
            return self._dependency_cache[spec]
        kwargs = await _collect_kwargs(spec.dependency, self)
        result = spec.dependency(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        if spec.use_cache:
            self._dependency_cache[spec] = result
        return result


def _extract_param_info(default: Any) -> ParamInfo | None:
    if isinstance(default, ParamInfo):
        return default
    return None


def _extract_dependency(default: Any) -> DependencySpec | None:
    if isinstance(default, DependencySpec):
        return default
    return None


def _is_request_param(name: str, anno: Any) -> bool:
    return name == "req" or anno is Request


def _query_key(name: str, info: ParamInfo | None) -> str | None:
    if info:
        if info.source == "query":
            return info.alias or name
        if info.source == "path":
            return None
    return name


def _coerce_or_raise(kind: str, name: str, raw: str, anno: Any) -> Any:
    try:
        return _coerce(raw, anno)
    except Exception:
        raise _ParamValidationError(f"invalid_{kind}_param", name, raw)


def _is_pydantic_model(anno: Any) -> bool:
    try:
        return inspect.isclass(anno) and issubclass(anno, BaseModel)
    except TypeError:
        return False


def _model_payload(ctx: _ResolverContext) -> Dict[str, Any]:
    if ctx._model_payload is not None:
        return ctx._model_payload
    payload: Dict[str, Any] = dict(ctx.query_params)
    for key, value in ctx.raw_path_params.items():
        payload.setdefault(key, value)
    ctx._model_payload = payload
    return payload


async def _collect_kwargs(handler: Handler | Callable[..., Any], ctx: _ResolverContext) -> Dict[str, Any]:
    sig = inspect.signature(handler)
    try:
        resolved_hints = get_type_hints(handler)
    except Exception:
        resolved_hints = {}

    kwargs: Dict[str, Any] = {}
    for name, param in sig.parameters.items():
        anno = resolved_hints.get(name, param.annotation)
        param_info = _extract_param_info(param.default)
        dependency = _extract_dependency(param.default)

        if dependency:
            kwargs[name] = await ctx.resolve_dependency(dependency)
            continue

        if _is_request_param(name, anno):
            kwargs[name] = ctx.request
            continue

        if _is_pydantic_model(anno):
            try:
                kwargs[name] = anno.model_validate(_model_payload(ctx))
            except ValidationError as exc:
                raise _ParamValidationError("invalid_model", name, exc.errors())
            continue

        if name in ctx.raw_path_params:
            raw = ctx.raw_path_params[name]
            kwargs[name] = _coerce_or_raise("path", param_info.alias or name if param_info and param_info.alias else name, raw, anno)
            continue

        query_name = _query_key(name, param_info)
        if query_name and query_name in ctx.query_params:
            raw = ctx.query_params[query_name]
            kwargs[name] = _coerce_or_raise("query", query_name, raw, anno)
            continue

        if param_info:
            if not param_info.required and param_info.default is not inspect._empty:
                kwargs[name] = param_info.default
                continue
            if param_info.required:
                raise _ParamValidationError("missing_query_param", param_info.alias or name)
            continue

        if param.default is not inspect._empty:
            kwargs[name] = param.default
            continue

        raise _ParamValidationError("missing_query_param", name)

    return kwargs


def _ensure_response(value: Any) -> Response:
    if isinstance(value, Response):
        return value
    if isinstance(value, BaseModel):
        return Response.json(value.model_dump())
    if isinstance(value, bytes):
        return Response.bytes(value)
    if isinstance(value, str):
        return Response.text(value)
    return Response.json(value)


class Router:
    def __init__(self):
        self._routes: List[_Route] = []

    def route(self, method: str, path_template: str):
        def decorator(fn: Handler) -> Handler:
            self.add(method, path_template, fn)
            return fn

        return decorator

    def get(self, path_template: str):
        return self.route("GET", path_template)

    def post(self, path_template: str):
        return self.route("POST", path_template)

    def put(self, path_template: str):
        return self.route("PUT", path_template)

    def patch(self, path_template: str):
        return self.route("PATCH", path_template)

    def delete(self, path_template: str):
        return self.route("DELETE", path_template)

    def options(self, path_template: str):
        return self.route("OPTIONS", path_template)

    def head(self, path_template: str):
        return self.route("HEAD", path_template)

    def add(self, method: str, path_template: str, handler: Handler) -> None:
        path = _normalize_template(path_template)
        regex, names = _compile_path(path)
        self._routes.append(_Route(method.upper(), path, regex, names, handler))

    def include_router(self, router: "Router", prefix: str = "") -> None:
        pref = _normalize_prefix(prefix)
        for route in router._routes:
            path = _join_paths(pref, route.template)
            regex, names = _compile_path(path)
            self._routes.append(_Route(route.method, path, regex, names, route.handler))

    async def dispatch(self, req: Request) -> Response:
        m = req.method.upper()
        p = req.path

        for route in self._routes:
            if route.method != m:
                continue
            match = route.regex.match(p)
            if not match:
                continue

            ctx = _ResolverContext(req, match.groupdict())
            try:
                kwargs = await _collect_kwargs(route.handler, ctx)
            except _ParamValidationError as exc:
                return exc.response

            result = await route.handler(**kwargs)
            return _ensure_response(result)

        return Response.text("Not Found\n", status=404)
