from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Pattern, Tuple, get_type_hints

from .request import Request
from .response import Response

Handler = Callable[..., Awaitable[Response]]

_PARAM_RE = re.compile(r"{([a-zA-Z_][a-zA-Z0-9_]*)}")


@dataclass(frozen=True)
class _Route:
    method: str
    template: str
    regex: Pattern[str]
    param_names: List[str]
    handler: Handler


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

            # Build kwargs for handler
            raw_params = match.groupdict()
            sig = inspect.signature(route.handler)
            try:
                resolved_hints = get_type_hints(route.handler)
            except Exception:
                resolved_hints = {}

            kwargs: Dict[str, Any] = {}
            for name, raw in raw_params.items():
                param = sig.parameters.get(name)
                anno = inspect._empty
                if param:
                    anno = resolved_hints.get(name, param.annotation)
                try:
                    kwargs[name] = _coerce(raw, anno)
                except Exception:
                    return Response.json(
                        {"error": "invalid_path_param", "param": name, "value": raw},
                        status=400,
                    )

            # Optional: inject query params by matching handler args
            # Example: def search(keyword: str = "") -> Response
            for pname, p in sig.parameters.items():
                if pname in kwargs:
                    continue
                anno = resolved_hints.get(pname, p.annotation)
                if pname == "req":
                    kwargs[pname] = req
                    continue
                if pname in req.query_params:
                    raw = req.query_params[pname]
                    try:
                        kwargs[pname] = _coerce(raw, anno)
                    except Exception:
                        return Response.json(
                            {"error": "invalid_query_param", "param": pname, "value": raw},
                            status=400,
                        )
                elif p.default is not inspect._empty:
                    kwargs[pname] = p.default

            return await route.handler(**kwargs)

        return Response.text("Not Found\n", status=404)
