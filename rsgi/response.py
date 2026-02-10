from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List, Tuple


@dataclass(frozen=True)
class Response:
    status: int
    headers: List[Tuple[str, str]]
    body: bytes

    @staticmethod
    def text(
        body: str,
        status: int = 200,
        content_type: str = "text/plain; charset=utf-8",
    ) -> "Response":
        return Response(status, [("content-type", content_type)], body.encode("utf-8"))

    @staticmethod
    def json(obj: Any, status: int = 200) -> "Response":
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return Response(status, [("content-type", "application/json; charset=utf-8")], data)
