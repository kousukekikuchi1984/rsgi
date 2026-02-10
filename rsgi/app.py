from __future__ import annotations

from .request import Request
from .router import Router


class RsgiApp:
    """
    Lightweight callable wrapper that Granian (or any RSGI host) can invoke.
    """

    def __init__(self, router: Router | None = None):
        self.router = router or Router()

    async def __call__(self, scope, proto):
        req = Request(scope)
        res = await self.router.dispatch(req)

        proto.response_bytes(
            status=res.status,
            headers=res.headers,
            body=res.body,
        )
