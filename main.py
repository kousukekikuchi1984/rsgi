from __future__ import annotations

from pydantic import Field

from rsgi import BaseModel, Depends, Request, RsgiApp

app = RsgiApp()


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True, "rsgi": True}


class User(BaseModel):
    id: int
    name: str


@app.get("/users/{id}")
async def get_user(id: int) -> User:
    # id is already coerced based on the annotation
    return User(id=id, name=f"user-{id}")


class SearchParams(BaseModel):
    keyword: str = Field(default="")
    limit: int = Field(default=10, ge=1, le=50)


@app.get("/search")
async def search(params: SearchParams) -> dict[str, object]:
    # keyword / limit are pulled from query params if present
    return {"keyword": params.keyword, "limit": params.limit, "results": []}


class RequestMeta(BaseModel):
    method: str
    path: str
    query: str
    client: tuple[str, int] | None
    server: tuple[str, int] | None
    host: str | None
    ua: str | None


async def request_metadata(req: Request) -> RequestMeta:
    return RequestMeta(
        method=req.method,
        path=req.path,
        query=req.query_string,
        client=req.client,
        server=req.server,
        host=req.header("host"),
        ua=req.header("user-agent"),
    )


@app.get("/inspect")
async def inspect_req(meta: RequestMeta = Depends(request_metadata)) -> RequestMeta:
    return meta
