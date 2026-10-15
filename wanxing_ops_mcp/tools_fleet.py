"""八工具面（design D3）：7 调用型 + 1 对话型，双凭据分型。

Bearer 从进站 MCP 请求取（get_http_request 原始头——fastmcp 4.1.0 的
get_http_headers 过滤 Authorization，家族坑）。对话型 turn 的 Bearer 即 caller key；
管理型 Bearer 即平台令牌——同一条进站头，按工具语义分派到不同上游面。
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastmcp import FastMCP

from .client import MISSING_CREDENTIAL_HINT, RegistryClient, RegistryError

TURN_RECEIPT_NOTE = (
    "注意：这是回执（agent 的即时答复），不是最终结果。工单型 agent 的查询约定"
    "（如 STATUS <单号>）见该 agent 的 AgentCard/技能文档。"
)


def _current_bearer() -> str | None:
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
    async def wanxing_agents_browse(
        page: int = 1,
        page_size: int = 50,
    ) -> Any:
        """浏览萬星公开 agent 目录（GET /api/wanxing/v1/agents）——公开读，无需凭据。

        仅返回 public agent（slug/名称/描述/版本/能力/技能）。分页 page/page_size
        （默认 50，上限 200）。空目录如实为空。
        """
        return await client.request(
            "GET", "/api/wanxing/v1/agents",
            bearer=_current_bearer() or "anonymous",
            params={"page": page, "page_size": page_size},
        )

    @mcp.tool
    async def wanxing_agent_card(agent_slug: str) -> Any:
        """读 agent 的 AgentCard（GET /api/wanxing/v1/a2a/{slug}/.well-known/agent-card.json）。

        含能力（streaming 等）、技能清单与调用约定——发起回合前先读它，
        工单型 agent 的 SUBMIT/STATUS 动词写在这里。
        """
        return await client.request(
            "GET",
            f"/api/wanxing/v1/a2a/{agent_slug}/.well-known/agent-card.json",
            bearer=_current_bearer() or "anonymous",
        )

    @mcp.tool
    async def wanxing_callers_list(pack_id: str, agent_id: str) -> Any:
        """读部署的 caller 允许清单（GET /api/packs/{packId}/deployments/{agentId}/callers）。

        管理面：以你的平台令牌执行，仅部署者/创作者（403 如实透传）。
        """
        return await client.request(
            "GET",
            f"/api/packs/{pack_id}/deployments/{agent_id}/callers",
            bearer=_current_bearer(),
        )

    @mcp.tool
    async def wanxing_callers_add(pack_id: str, agent_id: str, email: str) -> dict[str, Any]:
        """加 caller 进允许清单（POST 同上，body {email}）——显式写操作。

        email 必须已有计费账号：404 NO_SUB2API_ACCOUNT = 该邮箱还没在计费面板
        登录过（如实转述并指路 token.finddatatech.cloud）。仅部署者/创作者。
        """
        result = await client.request(
            "POST",
            f"/api/packs/{pack_id}/deployments/{agent_id}/callers",
            bearer=_current_bearer(),
            json_body={"email": email},
        )
        return {"added": True, "result": result}

    @mcp.tool
    async def wanxing_callers_remove(pack_id: str, agent_id: str, user_id: int) -> dict[str, Any]:
        """从允许清单移除 caller（DELETE 同上，body/query userId）——显式写操作。"""
        result = await client.request(
            "DELETE",
            f"/api/packs/{pack_id}/deployments/{agent_id}/callers",
            bearer=_current_bearer(),
            json_body={"userId": user_id},
        )
        return {"removed": True, "result": result}

    @mcp.tool
    async def wanxing_agent_pause(pack_id: str, agent_id: str) -> dict[str, Any]:
        """暂停部署的 agent（POST .../pause）——显式写操作，仅部署者/创作者。"""
        result = await client.request(
            "POST",
            f"/api/packs/{pack_id}/deployments/{agent_id}/pause",
            bearer=_current_bearer(),
        )
        return {"paused": True, "result": result}

    @mcp.tool
    async def wanxing_agent_resume(pack_id: str, agent_id: str) -> dict[str, Any]:
        """恢复暂停的 agent（POST .../resume）——显式写操作，仅部署者/创作者。"""
        result = await client.request(
            "POST",
            f"/api/packs/{pack_id}/deployments/{agent_id}/resume",
            bearer=_current_bearer(),
        )
        return {"resumed": True, "result": result}

    @mcp.tool
    async def wanxing_agent_turn(
        agent_slug: str,
        text: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """对 agent 发起一个 A2A 回合（POST /api/wanxing/v1/a2a/{slug}，message/send）——对话型。

        **凭据：caller key**（sk-，计费面板自铸；不是平台令牌）——计费按时长边界
        结算到你的 key。幂等：Idempotency-Key（缺省自动生成，24h 重放窗）。
        同步应答是**回执不是最终结果**（长活发生在 agent 回合里；查询约定见
        AgentCard）。错误如实转述：402=余额/窗口不足，409=该 agent 已有回合在跑
        （按 Retry-After 重试），423=已暂停，429=超调用者 RPM，404=无此 agent。
        """
        bearer = _current_bearer()
        if not bearer:
            raise RegistryError("missing_credential", 401, MISSING_CREDENTIAL_HINT)
        key = idempotency_key or f"wanxing-ops-mcp-{uuid.uuid4()}"
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": text}]}},
        }
        result = await client.request(
            "POST",
            f"/api/wanxing/v1/a2a/{agent_slug}",
            bearer=bearer,
            json_body=body,
            headers={"Idempotency-Key": key, "Content-Type": "application/json"},
        )
        return {"receipt": result, "idempotencyKey": key, "note": TURN_RECEIPT_NOTE}
