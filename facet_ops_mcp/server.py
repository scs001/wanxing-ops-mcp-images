"""FastMCP 组装 + ASGI 布线（鉴权门 + /health）。

不经过 Starlette 路由（mount 的路径改写会让鉴权门判断失真）：显式分发器
先比 /health，其余全部交给带门的 MCP 应用。
"""

from __future__ import annotations

from . import SERVER_NAME, tools_market
from .auth_gate import AuthGate, AuthGateMiddleware
from .client import RegistryClient
from .config import Settings

INSTRUCTIONS = (
    "谦面市场操作助手：浏览 pack 目录、读详情、查重、发布/更新/上下架。"
    "每个调用以你的 registry 凭据（壹座注入）执行，可见范围与权限由 registry 判定。"
    "错误如实透传（401=凭据失效需重连，403=无权限，404=无此条目，unreachable=registry 故障）；"
    "空结果如实为空，绝不编造。写操作（publish/update/toggle）前建议先查重并确认属主边界。"
)

_HEALTH_OK = b'{"status":"ok"}'


def create_server(settings: Settings | None = None) -> "FastMCP":
    from fastmcp import FastMCP

    settings = settings or Settings.from_env()
    mcp = FastMCP(SERVER_NAME, instructions=INSTRUCTIONS)
    client = RegistryClient(
        settings.registry_base_url, timeout_seconds=settings.timeout_seconds
    )
    tools_market.register(mcp, client)
    mcp._facet_ops_client = client  # build_app 复用同一实例
    mcp._facet_ops_settings = settings
    return mcp


def build_app(settings: Settings | None = None):
    """完整 ASGI 应用：/health 无门；其余（/mcp）走鉴权门。"""
    mcp = create_server(settings)
    client: RegistryClient = mcp._facet_ops_client
    settings_: Settings = mcp._facet_ops_settings
    mcp_app = mcp.http_app(path="/mcp")
    gate = AuthGateMiddleware(mcp_app, AuthGate(client, settings_.auth_cache_ttl_seconds))

    async def app(scope, receive, send):
        if scope.get("type") == "http":
            path = (scope.get("path") or "").rstrip("/")
            if path == "/health":
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": _HEALTH_OK})
                return
        await gate(scope, receive, send)

    return app
