"""FastMCP 组装 + ASGI 布线（鉴权门 + /health）——双面。

face=registry（facet-ops-mcp）：六工具包 registry 网关 AgentCard 面（/api/agents*）。
face=market（facet-market-mcp）：六工具包 facet 市场（/api/packs*）。
不经过 Starlette 路由（mount 的路径改写会让鉴权门判断失真）：显式分发器
先比 /health，其余全部交给带门的 MCP 应用。
"""

from __future__ import annotations

from . import SERVER_NAME, tools_market, tools_marketplane
from .auth_gate import AuthGate, AuthGateMiddleware
from .client import RegistryClient
from .config import Settings

INSTRUCTIONS_REGISTRY = (
    "谦面网关操作助手：浏览网关 AgentCard 目录、读详情、查重、登记/更新/启停。"
    "每个调用以你的 registry 凭据（壹座注入）执行，可见范围与权限由 registry 判定。"
    "错误如实透传（401=凭据失效需重连，403=无权限，404=无此条目，unreachable=registry 故障）；"
    "空结果如实为空，绝不编造。写操作前建议先查重并确认属主边界。"
)

INSTRUCTIONS_MARKET = (
    "谦面市场操作助手：浏览 pack 目录、读详情与版本、发布新 pack/新版本、"
    "切换可见性、设置策展分类。每个调用以你的市场凭据（壹座注入，设备配对铸造）执行，"
    "发布需 creators 组。错误如实透传（401=凭据失效需重连，403=无权限/需创作者组，"
    "404=无此 pack，400=清单校验失败带逐条错误）；空结果如实为空，绝不编造。"
    "发布是写操作：先浏览查重，manifest 按创作指南组装，仅作者可发新版本。"
)

_HEALTH_OK = b'{"status":"ok"}'


def create_server(settings: Settings | None = None) -> "FastMCP":
    from fastmcp import FastMCP

    settings = settings or Settings.from_env()
    if settings.face == "market":
        name, instructions, tools = "facet-market-mcp", INSTRUCTIONS_MARKET, tools_marketplane
    else:
        name, instructions, tools = SERVER_NAME, INSTRUCTIONS_REGISTRY, tools_market
    mcp = FastMCP(name, instructions=instructions)
    client = RegistryClient(
        settings.upstream_base_url, timeout_seconds=settings.timeout_seconds
    )
    tools.register(mcp, client)
    mcp._facet_ops_client = client  # build_app 复用同一实例
    mcp._facet_ops_settings = settings
    return mcp


def build_app(settings: Settings | None = None):
    """完整 ASGI 应用：/health 无门；其余（/mcp）走鉴权门（探针按面注入）。"""
    mcp = create_server(settings)
    client: RegistryClient = mcp._facet_ops_client
    settings_: Settings = mcp._facet_ops_settings
    mcp_app = mcp.http_app(path="/mcp")

    probe_path, _, query = settings_.auth_probe_path.partition("?")
    probe_params: dict = {}
    if query:
        for kv in query.split("&"):
            k, _, v = kv.partition("=")
            probe_params[k] = v
    gate = AuthGateMiddleware(
        mcp_app, AuthGate(client, settings_.auth_cache_ttl_seconds, probe_path, probe_params)
    )

    async def app(scope, receive, send):
        if scope.get("type") == "http":
            path = (scope.get("path") or "").rstrip("/")
            if path == "/health":
                import json as _json
                body = _json.dumps({
                    "status": "ok",
                    "server": "facet-market-mcp" if settings_.face == "market" else SERVER_NAME,
                    "face": settings_.face,
                    "upstream": settings_.upstream_base_url,
                }, ensure_ascii=False).encode()
                await send({"type": "http.response.start", "status": 200,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": body})
                return
        await gate(scope, receive, send)

    return app
