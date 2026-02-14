from __future__ import annotations

from typing import Awaitable, Callable, Iterable, List

from .request import Request
from .response import Response
from .router import Router

NextCallable = Callable[[Request], Awaitable[Response]]
Middleware = Callable[[Request, NextCallable], Awaitable[Response]]


class RsgiApp:
    """
    Lightweight callable wrapper that Granian (or any RSGI host) can invoke.

    Middlewares can be attached to intercept and mutate the request/response cycle.
    """

    def __init__(self, router: Router | None = None, middleware: Iterable[Middleware] | None = None):
        self.router = router or Router()
        self._middleware: List[Middleware] = list(middleware or [])

    def add_middleware(self, middleware: Middleware) -> None:
        self._middleware.append(middleware)

    def route(self, method: str, path_template: str):
        return self.router.route(method, path_template)

    def add_route(self, method: str, path_template: str, handler):
        self.router.add(method, path_template, handler)

    def include_router(self, router: Router, prefix: str = "") -> None:
        self.router.include_router(router, prefix)

    def get(self, path_template: str):
        return self.router.get(path_template)

    def post(self, path_template: str):
        return self.router.post(path_template)

    def put(self, path_template: str):
        return self.router.put(path_template)

    def patch(self, path_template: str):
        return self.router.patch(path_template)

    def delete(self, path_template: str):
        return self.router.delete(path_template)

    def options(self, path_template: str):
        return self.router.options(path_template)

    def head(self, path_template: str):
        return self.router.head(path_template)

    async def handle(self, req: Request) -> Response:
        async def call_router(request: Request) -> Response:
            return await self.router.dispatch(request)

        call_next: NextCallable = call_router
        for mw in reversed(self._middleware):
            call_next = self._wrap_middleware(mw, call_next)

        return await call_next(req)

    async def __call__(self, scope, proto):
        req = Request(scope)
        res = await self.handle(req)

        proto.response_bytes(
            status=res.status,
            headers=res.headers,
            body=res.body,
        )

    @staticmethod
    def _wrap_middleware(middleware: Middleware, call_next: NextCallable) -> NextCallable:
        async def _inner(request: Request) -> Response:
            return await middleware(request, call_next)

        return _inner
