"""六工具面（设计 D3）：facet_ 前缀、写操作显式、载荷薄转发。

Bearer 从进站 MCP 请求取（get_http_headers，家族先例 fd-open-data-mcp scoping.py）；
测试经 _current_bearer() 注入点 monkeypatch。
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from .client import RegistryClient, RegistryError


def _current_bearer() -> str | None:
    """进站 MCP 请求的 Bearer（无请求上下文/无头 → None）。"""
    try:
        from fastmcp.server.dependencies import get_http_headers
    except ImportError:  # 旧版 fastmcp
        return None
    headers = get_http_headers() or {}
    auth = (headers.get("Authorization") or headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def register(mcp: FastMCP, client: RegistryClient) -> None:
    @mcp.tool
    async def facet_catalog_browse(
        query: str | None = None,
        enabled_only: bool = False,
        visibility: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Any:
        """浏览谦面市场 pack 目录（GET /api/agents）。

        以调用方用户身份执行——可见范围（公开/私有/分组）由 registry 按该用户判定。
        query 支持名称/描述模糊匹配；分页 limit/offset（默认 20/0）。
        空结果如实返回空列表。
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            params["query"] = query
        if enabled_only:
            params["enabled_only"] = True
        if visibility:
            params["visibility"] = visibility
        return await client.request("GET", "/api/agents", bearer=_current_bearer(), params=params)

    @mcp.tool
    async def facet_pack_read(path: str, metadata_fields: list[str] | None = None) -> Any:
        """读取 pack 详情（GET /api/agents/{path}）。

        path 为市场条目路径（如 packs/<packId> 或注册名）；metadata_fields 可选，
        请求附加元数据字段（如 surface/marketplace）。404 如实报 not_found。
        """
        params = {"metadata_fields": metadata_fields} if metadata_fields else None
        return await client.request(
            "GET", f"/api/agents/{path}", bearer=_current_bearer(), params=params
        )

    @mcp.tool
    async def facet_pack_publish(registration: dict[str, Any]) -> dict[str, Any]:
        """发布/登记新 pack 到谦面市场（POST /api/agents/register）——写操作。

        registration 按 registry 契约薄转发：必填 name / url / supportedProtocol；
        常用可选：description、is_proxied（true=走网关路由，需配 proxy_target_url）、
        proxy_target_url、proxy_streaming。需要 registry 侧 publish_agent 权限（403
        如实透传）。建议先 facet_duplicate_check 查重。
        """
        result = await client.request(
            "POST", "/api/agents/register", bearer=_current_bearer(), json_body=registration
        )
        return {"published": True, "result": result}

    @mcp.tool
    async def facet_pack_update(path: str, registration: dict[str, Any]) -> dict[str, Any]:
        """更新已有 pack 定义/发新版本（PUT /api/agents/{path}）——写操作。

        registration 与 facet_pack_publish 同形（registry AgentRegistrationRequest）；
        仅条目属主/有权者可改（403 如实透传）。
        """
        result = await client.request(
            "PUT", f"/api/agents/{path}", bearer=_current_bearer(), json_body=registration
        )
        return {"updated": True, "result": result}

    @mcp.tool
    async def facet_pack_toggle(path: str, enabled: bool) -> dict[str, Any]:
        """上/下架 pack（POST /api/agents/{path}/toggle）——显式写操作。

        enabled=True 上架（对市场可见），False 下架（保留条目不删）。仅属主/有权者。
        """
        result = await client.request(
            "POST",
            f"/api/agents/{path}/toggle",
            bearer=_current_bearer(),
            params={"enabled": enabled},
        )
        return {"toggled": True, "enabled": enabled, "result": result}

    @mcp.tool
    async def facet_duplicate_check(
        name: str,
        description: str | None = None,
        url: str | None = None,
        self_path: str | None = None,
    ) -> Any:
        """发布前咨询式查重（POST /api/agents/check-duplicates）——恒 200，不阻塞。

        返回 collision_with（同 URL 精确命中）与 advisory_matches（相似命中）；
        有匹配也可继续发布（advisory 语义）。self_path 用于排除自身。
        """
        body: dict[str, Any] = {"name": name}
        if description:
            body["description"] = description
        if url:
            body["url"] = url
        if self_path:
            body["self_path"] = self_path
        return await client.request(
            "POST", "/api/agents/check-duplicates", bearer=_current_bearer(), json_body=body
        )
