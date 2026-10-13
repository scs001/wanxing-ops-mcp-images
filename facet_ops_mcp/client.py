"""registry console API 客户端：Bearer 转发 + 诚实错误映射。

设计 D2/D4：凭据只经手不落盘；401/403/404/409/422 透传状态码与 detail 原文；
连接失败/超时/5xx 归为 unreachable——不冒充业务错误。
"""

from __future__ import annotations

from typing import Any

import httpx


class RegistryError(Exception):
    """结构化错误：kind + status + registry detail 原文。"""

    def __init__(self, kind: str, status: int | None, detail: str):
        super().__init__(f"[{kind}] {detail}" + (f" (HTTP {status})" if status else ""))
        self.kind = kind
        self.status = status
        self.detail = detail


MISSING_CREDENTIAL_HINT = (
    "缺少 registry 凭据：请先在壹座「设置 → registry 凭据」连接（或粘贴）后再调用"
)


class RegistryClient:
    def __init__(self, base_url: str, timeout_seconds: float = 15.0, transport=None):
        # transport 注入供测试 mock；生产走真实 httpx
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
    ) -> Any:
        if not bearer:
            # 契约：无凭据不触上游
            raise RegistryError("missing_credential", 401, MISSING_CREDENTIAL_HINT)
        headers = {"Authorization": f"Bearer {bearer}"}
        try:
            res = await self._client.request(
                method, path, headers=headers, params=params, json=json_body
            )
        except httpx.HTTPError as e:
            raise RegistryError(
                "unreachable", None, f"registry 不可达：{type(e).__name__}: {e}"
            ) from e
        if res.status_code == 401:
            raise RegistryError("unauthorized", 401, _detail(res))
        if res.status_code == 403:
            raise RegistryError("forbidden", 403, _detail(res))
        if res.status_code == 404:
            raise RegistryError("not_found", 404, _detail(res))
        if res.status_code == 409:
            raise RegistryError("conflict", 409, _detail(res))
        if res.status_code == 422:
            raise RegistryError("invalid", 422, _detail(res))
        if res.status_code >= 500:
            raise RegistryError(
                "unreachable", res.status_code, f"registry 服务错误：{_detail(res)}"
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
    """registry detail 原文（FastAPI detail 字段或 body 文本），截断防膨胀。"""
    try:
        body = res.json()
        if isinstance(body, dict) and "detail" in body:
            d = body["detail"]
            return str(d)[:500]
        return str(body)[:500]
    except Exception:
        return (res.text or "")[:500] or f"HTTP {res.status_code}（无 body）"
