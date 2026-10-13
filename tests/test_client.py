"""client.py 契约测试：Bearer 转发 + 错误映射（mock transport）。"""

from __future__ import annotations

import httpx
import pytest

from facet_ops_mcp.client import MISSING_CREDENTIAL_HINT, RegistryClient, RegistryError


def make_client(handler) -> RegistryClient:
    transport = httpx.MockTransport(handler)
    return RegistryClient("https://reg.example", timeout_seconds=5, transport=transport)


async def test_bearer_forwarded_verbatim():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"agents": []})

    client = make_client(handler)
    result = await client.request(
        "GET", "/api/agents", bearer="tok-abc", params={"limit": 1}
    )
    assert seen["auth"] == "Bearer tok-abc"
    assert seen["path"] == "/api/agents"
    assert seen["params"]["limit"] == "1"
    assert result == {"agents": []}


async def test_missing_credential_never_touches_upstream():
    def handler(request):  # pragma: no cover - 到这里即失败
        raise AssertionError("无凭据不应触上游")

    client = make_client(handler)
    with pytest.raises(RegistryError) as ei:
        await client.request("GET", "/api/agents", bearer=None)
    assert ei.value.kind == "missing_credential"
    assert ei.value.status == 401
    assert MISSING_CREDENTIAL_HINT in ei.value.detail


@pytest.mark.parametrize(
    "status,kind",
    [
        (401, "unauthorized"),
        (403, "forbidden"),
        (404, "not_found"),
        (409, "conflict"),
        (422, "invalid"),
        (500, "unreachable"),
        (503, "unreachable"),
    ],
)
async def test_status_mapping(status, kind):
    def handler(request):
        return httpx.Response(status, json={"detail": f"boom {status}"})

    client = make_client(handler)
    with pytest.raises(RegistryError) as ei:
        await client.request("GET", "/api/agents", bearer="tok")
    assert ei.value.kind == kind
    assert ei.value.status == status
    assert f"boom {status}" in ei.value.detail  # detail 原文透传


async def test_transport_error_is_unreachable():
    def handler(request):
        raise httpx.ConnectError("refused")

    client = make_client(handler)
    with pytest.raises(RegistryError) as ei:
        await client.request("GET", "/api/agents", bearer="tok")
    assert ei.value.kind == "unreachable"
    assert ei.value.status is None
    assert "不可达" in ei.value.detail
