from __future__ import annotations

import asyncio
import json

from pydantic import BaseModel, Field

from rsgi import Depends, Query, Request, Response, Router, RsgiApp


class DummyScope:
    def __init__(self, method: str, path: str, query_string: str = ""):
        self.method = method
        self.path = path
        self.query_string = query_string
        self.headers = {}
        self.client = None
        self.server = None


async def _dispatch(router: Router, method: str, path: str, query_string: str = ""):
    req = Request(DummyScope(method, path, query_string=query_string))
    return await router.dispatch(req)


def dispatch(router: Router, method: str, path: str, query_string: str = ""):
    return asyncio.run(_dispatch(router, method, path, query_string=query_string))


def test_route_decorators_register_methods():
    router = Router()

    @router.get("/ping")
    async def ping() -> Response:
        return Response.text("pong")

    @router.post("/ping")
    async def ping_post() -> Response:
        return Response.json({"ok": True})

    res_get = dispatch(router, "GET", "/ping")
    assert res_get.status == 200
    assert res_get.body == b"pong"

    res_post = dispatch(router, "POST", "/ping")
    assert res_post.status == 200
    assert json.loads(res_post.body.decode()) == {"ok": True}


def test_include_router_with_prefix():
    parent = Router()
    sub = Router()

    @sub.get("/items/{item_id}")
    async def get_item(item_id: int) -> Response:
        return Response.json({"item_id": item_id})

    parent.include_router(sub, prefix="/api/v1")

    res = dispatch(parent, "GET", "/api/v1/items/42")
    assert res.status == 200
    assert json.loads(res.body.decode()) == {"item_id": 42}

    missing = dispatch(parent, "GET", "/items/42")
    assert missing.status == 404


def test_app_route_decorators_proxy_router():
    app = RsgiApp()

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    res = dispatch(app.router, "GET", "/ping")
    assert res.status == 200
    assert json.loads(res.body.decode()) == {"pong": True}


def test_handler_return_values_are_coerced():
    router = Router()

    @router.get("/dict")
    async def dict_response():
        return {"ok": True}

    @router.get("/text")
    async def text_response():
        return "hello"

    class Payload(BaseModel):
        ok: bool

    @router.get("/model")
    async def model_response():
        return Payload(ok=True)

    dict_res = dispatch(router, "GET", "/dict")
    assert dict_res.headers[0][1].startswith("application/json")
    assert json.loads(dict_res.body.decode()) == {"ok": True}

    text_res = dispatch(router, "GET", "/text")
    assert text_res.headers[0][1].startswith("text/plain")
    assert text_res.body == b"hello"

    model_res = dispatch(router, "GET", "/model")
    assert json.loads(model_res.body.decode()) == {"ok": True}


def test_query_alias_and_required_enforced():
    router = Router()

    @router.get("/search")
    async def search(keyword: str = Query(alias="q")):
        return {"keyword": keyword}

    ok = dispatch(router, "GET", "/search", query_string="q=rsgi")
    assert ok.status == 200
    assert json.loads(ok.body.decode()) == {"keyword": "rsgi"}

    missing = dispatch(router, "GET", "/search")
    assert missing.status == 400
    assert json.loads(missing.body.decode())["error"] == "missing_query_param"


class FiltersModel(BaseModel):
    keyword: str = ""
    limit: int = Field(default=5, ge=1, le=25)
    item_id: int


def test_pydantic_model_parameter_injected_from_query_and_path():
    router = Router()

    @router.get("/items/{item_id}")
    async def handler(filters: FiltersModel):
        return filters

    ok = dispatch(router, "GET", "/items/22", query_string="keyword=fast&limit=10")
    assert ok.status == 200
    assert json.loads(ok.body.decode()) == {"keyword": "fast", "limit": 10, "item_id": 22}

    invalid = dispatch(router, "GET", "/items/22", query_string="limit=100")
    assert invalid.status == 400
    detail = json.loads(invalid.body.decode())
    assert detail["error"] == "invalid_model"


def test_dependency_resolution_with_request_context():
    router = Router()

    async def keyword(req: Request) -> str:
        return req.query_params.get("keyword", "")

    @router.get("/items/{item_id}")
    async def handler(item_id: int, kw: str = Depends(keyword)):
        return {"item_id": item_id, "keyword": kw}

    res = dispatch(router, "GET", "/items/5", query_string="keyword=fast")
    assert res.status == 200
    assert json.loads(res.body.decode()) == {"item_id": 5, "keyword": "fast"}
