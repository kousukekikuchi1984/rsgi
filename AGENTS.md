# Repository Guidelines

This repo is a minimal Granian RSGI service with typed helpers and a lightweight router housed in `main.py`.

## Project Structure & Module Organization
- `main.py` defines `Request`/`Response`, the router, default handlers, and the exported `app` callable.
- `pyproject.toml` and `uv.lock` capture metadata plus pinned dependencies; update them with `uv` instead of hand-editing versions.
- Keep docs at the repo root and place future modules (e.g., `handlers/`, `router.py`) plus mirrored tests under `tests/` so features and coverage evolve together.

## Build, Test, and Development Commands
- `uv sync` — install the locked environment into `.venv`; rerun whenever dependencies change.
- `uv run granian --interface rsgi main:app` — launch the server and expose `/health`, `/users/{id}`, `/search`, and `/inspect`.
- `uv run pytest [-k pattern]` — execute async handler tests; pair with `--maxfail=1` or `-vv` while debugging.
- `uv run python -m main` — smoke-check imports and module-level code for quick feedback.

## Coding Style & Naming Conventions
Use 4-space indentation, exhaustive type hints, and dataclasses for structured payloads as shown in `Request`. Keep router handlers async, snake_case, and descriptive (`search`, `inspect_req`). Return `Response.text/json` instead of bare dicts so serialization stays centralized, and split helpers into dedicated files when they push a module past ~200 lines.

## Testing Guidelines
Favor `pytest` with `pytest.mark.asyncio` for coroutine handlers and stick to `tests/test_<feature>.py` naming. Create small fake scope objects to validate header parsing, query params, and `_coerce` conversions. Maintain ≥80% coverage via `uv run pytest --cov=main --cov-report=term-missing` to catch regressions in routing and parameter coercion.

## Commit & Pull Request Guidelines
Commits should follow the existing lowercase imperative style (e.g., `add rsgi project`), keep summaries ≤72 chars, and include concise bodies describing rationale plus testing. PRs must reference an issue or task, call out new routes or breaking API changes, and list manual checks like `uv run granian --interface rsgi main:app`. Request review before merging—even for doc updates—so routing guarantees stay intact.

## Security & Configuration Tips
Validate untrusted headers before echoing them (the `/inspect` handler is debugging only) and remove temporary routes from release branches. Configure Granian via env vars such as `GRANIAN_HTTP_PORT` and `GRANIAN_WORKERS`, and rely on secrets managers rather than checking credentials into `pyproject.toml`.
