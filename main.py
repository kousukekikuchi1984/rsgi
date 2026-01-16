from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Pattern, Tuple
from urllib.parse import parse_qs


# ----------------------------
# Request / Response
# ----------------------------

@dataclass(frozen=True)
class Request:
    scope: object

    @property
    def method(self) -> str:
        return getattr(self.scope, "method")

    @property
    def path(self) -> str:
        return getattr(self.scope, "path")

    @property
    def query_string(self) -> str:
        return getattr(self.scope, "query_string") or ""

    @property
    def query_params(self) -> Dict[str, str]:
        parsed = parse_qs(self.query_string, keep_blank_values=True)
        return {k: (v[0] if v else "") for k, v in parsed.items()}

    @property
    def headers(self):
        # RSGIHeaders: get/get_all/items/keys/values
        return getattr(self.scope, "headers")

    def header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        h = self.headers
        v = h.get(name, None)
        if v is not None:
            return str(v)
        name_l = name.lower()
        for k, vv in h.items():
            if str(k).lower() == name_l:
                return str(vv)
        return default

    @property
    def client(self) -> Optional[Tuple[str, int]]:
        raw = getattr(self.scope, "client", None)
        if not raw:
            return None
        host, port = raw.rsplit(":", 1)
        return host, int(port)

    @property
    def server(self) -> Optional[Tuple[str, int]]:
        raw = getattr(self.scope, "server", None)
        if not raw:
            return None
        host, port = raw.rsplit(":", 1)
        return host, int(port)


@dataclass(frozen=True)
class Response:
    status: int
    headers: List[Tuple[str, str]]
    body: bytes

    @staticmethod
    def text(body: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> "Response":
        return Response(status, [("content-type", content_type)], body.encode("utf-8"))

    @staticmethod
    def json(obj: Any, status: int = 200) -> "Response":
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return Response(status, [("content-type", "application/json; charset=utf-8")], data)


# ----------------------------
# Router with path params
# ----------------------------

Handler = Callable[..., Awaitable[Response]]

_PARAM_RE = re.compile(r"{([a-zA-Z_][a-zA-Z0-9_]*)}")

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
        # Each route: (method, template, regex, param_names, handler)
        self._routes: List[Tuple[str, str, Pattern[str], List[str], Handler]] = []

    def get(self, path_template: str):
        def decorator(fn: Handler) -> Handler:
            self.add("GET", path_template, fn)
            return fn
        return decorator

    def add(self, method: str, path_template: str, handler: Handler) -> None:
        regex, names = _compile_path(path_template)
        self._routes.append((method.upper(), path_template, regex, names, handler))

    async def dispatch(self, req: Request) -> Response:
        m = req.method.upper()
        p = req.path

        for method, _tmpl, regex, _names, handler in self._routes:
            if method != m:
                continue
            match = regex.match(p)
            if not match:
                continue

            # Build kwargs for handler
            raw_params = match.groupdict()
            sig = inspect.signature(handler)

            kwargs: Dict[str, Any] = {}
            for name, raw in raw_params.items():
                param = sig.parameters.get(name)
                anno = param.annotation if param else inspect._empty
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
                if pname == "req":
                    kwargs[pname] = req
                    continue
                if pname in req.query_params:
                    raw = req.query_params[pname]
                    try:
                        kwargs[pname] = _coerce(raw, p.annotation)
                    except Exception:
                        return Response.json(
                            {"error": "invalid_query_param", "param": pname, "value": raw},
                            status=400,
                        )
                elif p.default is not inspect._empty:
                    kwargs[pname] = p.default

            return await handler(**kwargs)

        return Response.text("Not Found\n", status=404)


router = Router()

# ----------------------------
# Example endpoints
# ----------------------------

@router.get("/health")
async def health() -> Response:
    return Response.json({"ok": True, "rsgi": True})

@router.get("/users/{id}")
async def get_user(id: int) -> Response:
    # id is already coerced to int because of the annotation
    return Response.json({"user": {"id": id, "name": f"user-{id}"}})

@router.get("/search")
async def search(keyword: str = "", limit: int = 10) -> Response:
    # keyword / limit are pulled from query params if present
    return Response.json({"keyword": keyword, "limit": limit, "results": []})

@router.get("/inspect")
async def inspect_req(req: Request) -> Response:
    return Response.json(
        {
            "method": req.method,
            "path": req.path,
            "query": req.query_string,
            "client": req.client,
            "server": req.server,
            "host": req.header("host"),
            "ua": req.header("user-agent"),
        }
    )


# ----------------------------
# Granian RSGI entrypoint
# ----------------------------

async def app(scope, proto):
    req = Request(scope)
    res = await router.dispatch(req)

    proto.response_bytes(
        status=res.status,
        headers=res.headers,
        body=res.body,
    )
