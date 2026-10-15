"""萬星对客 HTTP 客户端：Bearer 转发 + 诚实错误映射。

家族同款（facet-ops-mcp/client.py）；萬星特有：
- 402 = 计费门拒绝（INSUFFICIENT_BALANCE / CALLER_SUSPENDED）→ kind=billing
- 409 = TURN_IN_FLIGHT → kind=conflict（带 Retry-After 语义转述）
- 423 = AGENT_PAUSED → kind=paused
凭据只经手不落盘；连接失败/5xx=unreachable。
"""

from __future__ import annotations

from typing import Any

import httpx


class RegistryError(Exception):
    """结构化错误：kind + status + 上游 detail 原文。"""

    def __init__(self, kind: str, status: int | None, detail: str):
        super().__init__(f"[{kind}] {detail}" + (f" (HTTP {status})" if status else ""))
        self.kind = kind
        self.status = status
        self.detail = detail


MISSING_CREDENTIAL_HINT = (
    "缺少凭据：管理面工具需要壹座平台令牌；wanxing_agent_turn 需要 caller key"
    "（在计费面板 token.finddatatech.cloud 自铸 sk-）"
)


class RegistryClient:
    def __init__(self, base_url: str, timeout_seconds: float = 15.0, transport=None):
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout_seconds, transport=transport
        )

    async def aclose(self):
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        bearer: str | None,
        params: dict | None = None,
        json_body: Any | None = None,
        headers: dict | None = None,
    ) -> Any:
        if not bearer:
            raise RegistryError("missing_credential", 401, MISSING_CREDENTIAL_HINT)
        req_headers = {"Authorization": f"Bearer {bearer}"}
        if headers:
            req_headers.update(headers)
        try:
            res = await self._client.request(
                method, path, headers=req_headers, params=params, json=json_body
            )
        except httpx.HTTPError as e:
            raise RegistryError(
                "unreachable", None, f"萬星服务不可达：{type(e).__name__}: {e}"
            ) from e
        if res.status_code == 401:
            raise RegistryError("unauthorized", 401, _detail(res))
        if res.status_code == 402:
            raise RegistryError("billing", 402, _detail(res))
        if res.status_code == 403:
            raise RegistryError("forbidden", 403, _detail(res))
        if res.status_code == 404:
            raise RegistryError("not_found", 404, _detail(res))
        if res.status_code == 409:
            raise RegistryError("conflict", 409, _detail(res))
        if res.status_code == 422:
            raise RegistryError("invalid", 422, _detail(res))
        if res.status_code == 423:
            raise RegistryError("paused", 423, _detail(res))
        if res.status_code == 429:
            raise RegistryError("rate_limited", 429, _detail(res))
        if res.status_code >= 500:
            raise RegistryError(
                "unreachable", res.status_code, f"萬星服务错误：{_detail(res)}"
            )
        if res.status_code >= 400:
            raise RegistryError("invalid", res.status_code, _detail(res))
        if not res.content:
            return None
        try:
            return res.json()
        except ValueError:
            return {"_raw": res.text}


def _detail(res: httpx.Response) -> str:
    try:
        body = res.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])[:500]
        if isinstance(body, dict) and "error" in body:
            return str(body["error"])[:500]
        return str(body)[:500]
    except Exception:
        return (res.text or "")[:500] or f"HTTP {res.status_code}（无 body）"
