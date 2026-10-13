"""市场面六工具（facet_market_*）：薄包 facet 市场 /api/packs*。

Bearer 从进站 MCP 请求取（get_http_request 原始头，同 tools_market 的坑）；
凭据=市场平台 app token（壹座 facet-market ref 注入——设备密钥静默续登铸造）。
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from .client import RegistryClient, RegistryError


def _current_bearer() -> str | None:
    """进站 MCP 请求的 Bearer（fastmcp 4.1.0 get_http_headers 过滤 Authorization，
    必须从 get_http_request().headers 原始头取——tools_market 同坑）。"""
    try:
        from fastmcp.server.dependencies import get_http_request
    except ImportError:
        return None
    req = get_http_request()
    if req is None:
        return None
    auth = (req.headers.get("Authorization") or req.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def register(mcp: FastMCP, client: RegistryClient) -> None:
    @mcp.tool
    async def facet_market_pack_browse(
        search: str | None = None,
        tag: str | None = None,
        category: str | None = None,
        author_me: bool = False,
        page: int = 1,
        pageSize: int = 20,
    ) -> Any:
        """浏览谦面市场 pack 目录（GET /api/packs）——当前有效版本列表。

        search 模糊匹配名称/描述；tag/category 过滤；author_me=true 只看
        我发布的（创作者台同款）；分页 page/pageSize。空结果如实为空。
        """
        params: dict[str, Any] = {"page": page, "pageSize": pageSize}
        if search:
            params["search"] = search
        if tag:
            params["tag"] = tag
        if category:
            params["category"] = category
        if author_me:
            params["author"] = "me"
        return await client.request("GET", "/api/packs", bearer=_current_bearer(), params=params)

    @mcp.tool
    async def facet_market_pack_read(id: str) -> Any:
        """读 pack 详情（GET /api/packs/{id}）——最新版本清单+作者视角订阅数。

        私有包对非作者应答 404（探测不泄密，属市场既有语义）。
        """
        return await client.request("GET", f"/api/packs/{id}", bearer=_current_bearer())

    @mcp.tool
    async def facet_market_pack_versions(id: str) -> Any:
        """读 pack 版本历史（GET /api/packs/{id}/versions）——可见性与详情同判。"""
        return await client.request("GET", f"/api/packs/{id}/versions", bearer=_current_bearer())

    @mcp.tool
    async def facet_market_pack_publish(manifest: dict[str, Any], packId: str | None = None) -> dict[str, Any]:
        """发布 pack 到谦面市场（POST /api/packs）——写操作，头牌能力。

        manifest 为完整功能集清单（技能内联+MCP 引用+persona；schema 单一事实源
        =壹座 lib/pack-manifest.js 校验器与《创作与发布功能集》指南）。首次发布
        省略 packId（铸新 id）；发新版本传 packId（仅作者）。需要 creators 组
        （403 如实透传）；声明了工具名的 manifest 会过工具声明门（对不上 400）；
        仅通过校验的发布计入配额。建议先 facet_market_pack_browse 查重。
        """
        body: dict[str, Any] = {"manifest": manifest}
        if packId:
            body["packId"] = packId
        result = await client.request("POST", "/api/packs", bearer=_current_bearer(), json_body=body)
        return {"published": True, "result": result}

    @mcp.tool
    async def facet_market_pack_visibility(id: str, visibility: str) -> dict[str, Any]:
        """切 pack 可见性（PUT /api/packs/{id}/visibility）——显式写操作。

        visibility ∈ "public" | "private"；仅作者或管理员（403 如实透传）。
        """
        result = await client.request(
            "PUT", f"/api/packs/{id}/visibility",
            bearer=_current_bearer(), json_body={"visibility": visibility},
        )
        return {"visibility": visibility, "result": result}

    @mcp.tool
    async def facet_market_pack_curation(
        id: str, category: str | None = None, featured: bool | None = None
    ) -> dict[str, Any]:
        """策展信息（PUT /api/packs/{id}/curation）——写操作。

        category=slug（0-32 位 [a-z0-9-]，仅作者）；featured 仅管理员。403 如实透传。
        """
        body: dict[str, Any] = {}
        if category is not None:
            body["category"] = category
        if featured is not None:
            body["featured"] = featured
        result = await client.request(
            "PUT", f"/api/packs/{id}/curation", bearer=_current_bearer(), json_body=body
        )
        return {"curated": True, "result": result}
