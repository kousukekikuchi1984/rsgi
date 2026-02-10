from __future__ import annotations

import asyncio

from rsgi import Middleware, Request, Response, Router, RsgiApp


class DummyScope:
    def __init__(self, method: str, path: str):
        self.method = method
        self.path = path
        self.query_string = ""
        self.headers = {}
        self.client = None
        self.server = None


def make_request(method: str = "GET", path: str = "/") -> Request:
    return Request(DummyScope(method, path))


def run_app(app: RsgiApp, req: Request) -> Response:
    return asyncio.run(app.handle(req))


def test_middleware_order_and_mutation():
    router = Router()

    @router.get("/hello")
    async def hello() -> Response:
        return Response(200, [("content-type", "text/plain")], b"hi")

    order: list[str] = []

    async def mw1(request: Request, call_next):
        order.append("mw1-before")
        resp = await call_next(request)
        order.append("mw1-after")
        headers = list(resp.headers)
        headers.append(("x-mw1", "1"))
        return Response(resp.status, headers, resp.body)

    async def mw2(request: Request, call_next):
        order.append("mw2-before")
        resp = await call_next(request)
        order.append("mw2-after")
        headers = list(resp.headers)
        headers.append(("x-mw2", "1"))
        return Response(resp.status, headers, resp.body)

    app = RsgiApp(router, middleware=[mw1])
    app.add_middleware(mw2)

    res = run_app(app, make_request(path="/hello"))

    assert order == ["mw1-before", "mw2-before", "mw2-after", "mw1-after"]
    assert ("x-mw2", "1") in res.headers
    assert ("x-mw1", "1") in res.headers


def test_middleware_short_circuit():
    router = Router()

    @router.get("/hello")
    async def hello() -> Response:
        return Response.text("hi")

    async def guard(_: Request, __):
        return Response.text("blocked", status=401)

    app = RsgiApp(router, middleware=[guard])

    res = run_app(app, make_request(path="/hello"))

    assert res.status == 401
    assert res.body == b"blocked"
