"""HTTP 层鉴权门（ASGI 中间件）——双面参数化。

为什么在 HTTP 层而不只在工具层：壹座 preflight 探针（mcp-preflight.js）用注入头打
initialize，401 → auth-rejected 可见态；台账判据「匿名 POST initialize → 401 = 在路由」
也依赖它。门语义：

  - 请求无 Authorization → 401（匿名探活判据）
  - 有 Authorization → 上游轻校验（GET probe_path 带 Bearer），短 TTL 缓存按
    token 哈希键控；上游 401 → 401 透传（凭据失效在探针可见）
  - 上游不可达 → 放行（5xx 照存纪律：探针故障不当凭据失效；工具层会诚实报不可达）

凭据永不落日志：缓存键 = sha256(token)。
"""

from __future__ import annotations

import hashlib
import time

from .client import RegistryClient, RegistryError


class AuthGate:
    def __init__(
        self,
        client: RegistryClient,
        ttl_seconds: float = 60.0,
        probe_path: str = "/api/agents",
        probe_params: dict | None = None,
    ):
        self._client = client
        self._ttl = ttl_seconds
        self._probe_path = probe_path
        self._probe_params = probe_params or {"limit": 1}
        self._cache: dict[str, tuple[float, bool]] = {}

    def _key(self, bearer: str) -> str:
        return hashlib.sha256(bearer.encode()).hexdigest()

    async def check(self, bearer: str | None) -> bool:
        """True=放行；False=401。"""
        if not bearer:
            return False
        key = self._key(bearer)
        now = time.monotonic()
        hit = self._cache.get(key)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        ok = True
        try:
            await self._client.request(
                "GET", self._probe_path, bearer=bearer, params=self._probe_params
            )
        except RegistryError as e:
            if e.kind == "unauthorized":
                ok = False  # 上游判定凭据失效 → 401
            # unreachable/其他 → 放行（工具层诚实报错）
        self._cache[key] = (now, ok)
        return ok


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
