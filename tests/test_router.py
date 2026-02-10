from __future__ import annotations

import asyncio
import json

from rsgi import Request, Response, Router


class DummyScope:
    def __init__(self, method: str, path: str):
        self.method = method
        self.path = path
        self.query_string = ""
        self.headers = {}
        self.client = None
        self.server = None


async def _dispatch(router: Router, method: str, path: str):
    req = Request(DummyScope(method, path))
    return await router.dispatch(req)


def dispatch(router: Router, method: str, path: str):
    return asyncio.run(_dispatch(router, method, path))


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
