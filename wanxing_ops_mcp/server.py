"""FastMCP 组装 + ASGI 布线（鉴权门 + /health）。"""

from __future__ import annotations

from . import SERVER_NAME, tools_fleet
from .auth_gate import AuthGate, AuthGateMiddleware
from .client import RegistryClient
from .config import Settings

INSTRUCTIONS = (
    "萬星舰队操作助手：浏览公开 agent 目录、读卡片、部署者管允许清单与启停、"
    "以 caller key 发起 A2A 回合。回合的同步应答是回执不是最终结果——工单型 agent "
    "的查询约定在各自卡片里。错误如实透传（401=凭据失效、402=计费门拒绝、403=无权限、"
    "404=无此条目/无计费账号、409=回合在跑按 Retry-After 重试、423=已暂停、429=超频）；"
    "空目录如实为空，绝不编造 agent 或结果。写操作（callers/pause/resume）前先读现状确认。"
)

_HEALTH_OK = b'{"status":"ok"}'


def create_server(settings: Settings | None = None) -> "FastMCP":
    from fastmcp import FastMCP

    settings = settings or Settings.from_env()
    mcp = FastMCP(SERVER_NAME, instructions=INSTRUCTIONS)
    client = RegistryClient(settings.base_url, timeout_seconds=settings.timeout_seconds)
    tools_fleet.register(mcp, client)
    mcp._wanxing_ops_client = client
    mcp._wanxing_ops_settings = settings
    return mcp


def build_app(settings: Settings | None = None):
    """完整 ASGI 应用：/health 无门；其余（/mcp）走鉴权门（无 Bearer 拒）。"""
    mcp = create_server(settings)
    settings_: Settings = mcp._wanxing_ops_settings
    mcp_app = mcp.http_app(path="/mcp")
    gate = AuthGateMiddleware(mcp_app, AuthGate(settings_.auth_cache_ttl_seconds))

    async def app(scope, receive, send):
        if scope.get("type") == "http":
            path = (scope.get("path") or "").rstrip("/")
            if path == "/health":
                await send({"type": "http.response.start", "status": 200,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": _HEALTH_OK})
                return
        await gate(scope, receive, send)

    return app
