"""client 契约测试：Bearer 转发 + 萬星特有错误映射（402/409/423/429）。"""

from __future__ import annotations

import httpx
import pytest

from wanxing_ops_mcp.client import MISSING_CREDENTIAL_HINT, RegistryClient, RegistryError


def make_client(handler) -> RegistryClient:
    return RegistryClient("https://wanxing.example", timeout_seconds=5,
                          transport=httpx.MockTransport(handler))


async def test_bearer_forwarded_and_idempotency_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["idem"] = request.headers.get("Idempotency-Key")
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler)
    await client.request("POST", "/api/wanxing/v1/a2a/x", bearer="sk-tok",
                         json_body={}, headers={"Idempotency-Key": "abc"})
    assert seen["auth"] == "Bearer sk-tok"
    assert seen["idem"] == "abc"


async def test_missing_credential_never_touches_upstream():
    def handler(request):
        raise AssertionError("无凭据不应触上游")

    client = make_client(handler)
    with pytest.raises(RegistryError) as ei:
        await client.request("GET", "/x", bearer=None)
    assert ei.value.kind == "missing_credential"
    assert MISSING_CREDENTIAL_HINT in ei.value.detail


@pytest.mark.parametrize(
    "status,kind",
    [(401, "unauthorized"), (402, "billing"), (403, "forbidden"), (404, "not_found"),
     (409, "conflict"), (422, "invalid"), (423, "paused"), (429, "rate_limited"),
     (500, "unreachable"), (503, "unreachable")],
)
async def test_status_mapping(status, kind):
    def handler(request):
        return httpx.Response(status, json={"error": f"boom {status}"})

    client = make_client(handler)
    with pytest.raises(RegistryError) as ei:
        await client.request("GET", "/x", bearer="tok")
    assert ei.value.kind == kind
    assert ei.value.status == status
    assert f"boom {status}" in ei.value.detail


async def test_transport_error_is_unreachable():
    def handler(request):
        raise httpx.ConnectError("refused")

    client = make_client(handler)
    with pytest.raises(RegistryError) as ei:
        await client.request("GET", "/x", bearer="tok")
    assert ei.value.kind == "unreachable"
    assert "不可达" in ei.value.detail
