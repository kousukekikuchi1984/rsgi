## Overview

`rsgi` is an experimental FastAPI-like framework that targets the Granian RSGI interface. It provides typed request/response helpers, an async router with automatic parameter coercion, and a lightweight application container so you can build JSON or HTML APIs without depending on ASGI.

## Features

- **Modular core**: `Request`, `Response`, and `Router` live under the `rsgi` package and are importable from `rsgi.__init__`.
- **Routing ergonomics**: Decorators like `@router.get`/`post`/`include_router` support FastAPI-style handler definitions and namespaced routers.
- **FastAPI-like helpers**: `RsgiApp` exposes the HTTP decorators directly (so you can `@app.get`), handlers may return dicts/strings/bytes/Pydantic models that are auto-coerced into `Response` objects, and helper factories (`Query`, `Path`, `Depends`) bring aliasing plus lightweight dependency injection.
- **Pydantic ready**: `BaseModel` ships as a first-class dependency; annotate handler parameters with models to validate/coerce query + path params, or return models directly for JSON serialization.
- **Middleware pipeline**: `RsgiApp` composes middleware callables before invoking the router, enabling logging, auth, or metrics hooks.
- **Rich responses**: Built-in helpers cover text, JSON, HTML, template rendering (Jinja2), and optional accelerators (`UJSONResponse`, `ORJSONResponse`, `MsgPackResponse`).
- **Templating**: `TemplateEngine` wraps Jinja2 environments; `TemplateResponse` renders named templates and handles content types automatically.
- **Composable entrypoint**: `main.py` shows a canonical router/app setup that Granian can load via `main:app`.

## Quick Start

```bash
uv sync
uv run granian --interface rsgi main:app
```

Visit `http://localhost:8000/health` to confirm the sample routes respond.

## Development Notes

- Tests live under `tests/` and can be run with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest`.
- Optional dependencies (Jinja2, ujson, orjson, msgpack) are only required if you use their corresponding helpers; tests skip automatically when they are absent.
- Middleware functions follow the signature `async def middleware(request, call_next) -> Response` and can be registered via `RsgiApp(..., middleware=[...])` or `app.add_middleware`.
