from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs


@dataclass(frozen=True)
class Request:
    scope: object

    @property
    def method(self) -> str:
        return getattr(self.scope, "method")

    @property
    def path(self) -> str:
        return getattr(self.scope, "path")

    @property
    def query_string(self) -> str:
        return getattr(self.scope, "query_string") or ""

    @property
    def query_params(self) -> Dict[str, str]:
        parsed = parse_qs(self.query_string, keep_blank_values=True)
        return {k: (v[0] if v else "") for k, v in parsed.items()}

    @property
    def headers(self):
        # RSGIHeaders: get/get_all/items/keys/values
        return getattr(self.scope, "headers")

    def header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        h = self.headers
        v = h.get(name, None)
        if v is not None:
            return str(v)
        name_l = name.lower()
        for k, vv in h.items():
            if str(k).lower() == name_l:
                return str(vv)
        return default

    @property
    def client(self) -> Optional[Tuple[str, int]]:
        raw = getattr(self.scope, "client", None)
        if not raw:
            return None
        host, port = raw.rsplit(":", 1)
        return host, int(port)

    @property
    def server(self) -> Optional[Tuple[str, int]]:
        raw = getattr(self.scope, "server", None)
        if not raw:
            return None
        host, port = raw.rsplit(":", 1)
        return host, int(port)
