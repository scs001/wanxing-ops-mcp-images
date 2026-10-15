"""HTTP 层鉴权门（ASGI 中间件）。

萬星特化（design D2）：对客面只有公开读+凭据面，没有「轻校验端点」——门语义：
无 Bearer 的 POST /mcp 一律 401（匿名探活判据+台账判据）；有 Bearer 放行
（工具层对坏凭据诚实报错）。上游对坏 token 的 401 在工具层原样透传。
凭据永不落日志（缓存键 = sha256(token)）。
"""

from __future__ import annotations

import hashlib
import time


class AuthGate:
    """有 Bearer 即放行（探针不可用时的家族变体；语义收窄在 spec 已声明）。"""

    def __init__(self, ttl_seconds: float = 60.0):
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, bool]] = {}

    def _key(self, bearer: str) -> str:
        return hashlib.sha256(bearer.encode()).hexdigest()

    async def check(self, bearer: str | None) -> bool:
        if not bearer:
            return False
        key = self._key(bearer)
        now = time.monotonic()
        hit = self._cache.get(key)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        self._cache[key] = (now, True)
        return True


class AuthGateMiddleware:
    """薄 ASGI 包装：仅拦 POST /mcp*，其余原样放行（/health 无门）。"""

    def __init__(self, app, gate: AuthGate):
        self.app = app
        self.gate = gate

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        path = (scope.get("path") or "").lstrip("/")
        if path != "mcp" and not path.endswith("/mcp"):
            await self.app(scope, receive, send)
            return
        bearer = _bearer_from_scope(scope)
        if await self.gate.check(bearer):
            await self.app(scope, receive, send)
            return
        # 消掉上行 body 再应答，防连接悬挂：读到完整 request 或对端断开即止
        while True:
            msg = await receive()
            if msg.get("type") == "http.disconnect":
                return
            if msg.get("type") == "http.request" and not msg.get("more_body", False):
                break
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'{"error": "Authentication required"}',
            }
        )


def _bearer_from_scope(scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            text = value.decode("latin-1")
            if text.lower().startswith("bearer "):
                return text[7:].strip() or None
    return None
