from __future__ import annotations

from rsgi import Request, Response, Router, RsgiApp


router = Router()


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


app = RsgiApp(router)
