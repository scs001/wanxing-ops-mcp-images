"""六工具接线测试：方法/路径/参数/载荷薄转发 + 错误透传（fake client + 内存 Client）。"""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP

import facet_ops_mcp.tools_market as tm
from facet_ops_mcp.client import RegistryError


class FakeClient:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result
        self.error = error

    async def request(self, method, path, *, bearer, params=None, json_body=None):
        self.calls.append(
            {"method": method, "path": path, "bearer": bearer,
             "params": params, "json_body": json_body}
        )
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def bearer(monkeypatch):
    monkeypatch.setattr(tm, "_current_bearer", lambda: "user-token")
    return "user-token"


async def _mk(fake):
    mcp = FastMCP("t")
    tm.register(mcp, fake)
    return mcp


async def test_catalog_browse_forwards_pagination(bearer):
    fake = FakeClient(result=[])
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        result = await c.call_tool(
            "facet_catalog_browse", {"query": "法律", "limit": 5, "offset": 10}
        )
    call = fake.calls[0]
    assert call["method"] == "GET" and call["path"] == "/api/agents"
    assert call["bearer"] == "user-token"
    assert call["params"] == {"limit": 5, "offset": 10, "query": "法律"}


async def test_pack_read_path(bearer):
    fake = FakeClient(result={"name": "x"})
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        await c.call_tool("facet_pack_read", {"path": "packs/abc"})
    assert fake.calls[0]["path"] == "/api/agents/packs/abc"


async def test_publish_thin_forward(bearer):
    reg = {"name": "市场助手", "url": "https://x", "supportedProtocol": "mcp"}
    fake = FakeClient(result={"path": "packs/new"})
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        out = await c.call_tool("facet_pack_publish", {"registration": reg})
    call = fake.calls[0]
    assert call["method"] == "POST" and call["path"] == "/api/agents/register"
    assert call["json_body"] == reg  # 载荷薄转发，不改写


async def test_toggle_explicit_write(bearer):
    fake = FakeClient(result={"ok": True})
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        await c.call_tool("facet_pack_toggle", {"path": "packs/abc", "enabled": False})
    call = fake.calls[0]
    assert call["method"] == "POST"
    assert call["params"] == {"enabled": False}


async def test_duplicate_check_advisory_body(bearer):
    fake = FakeClient(result={"collision_with": None, "advisory_matches": []})
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        out = await c.call_tool(
            "facet_duplicate_check", {"name": "n", "url": "https://u"}
        )
    assert fake.calls[0]["json_body"] == {"name": "n", "url": "https://u"}
    assert out.data == {"collision_with": None, "advisory_matches": []}


async def test_registry_401_propagates_as_tool_error(bearer):
    fake = FakeClient(error=RegistryError("unauthorized", 401, "expired"))
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        with pytest.raises(Exception) as ei:
            await c.call_tool("facet_catalog_browse", {})
    assert "expired" in str(ei.value)  # detail 原文可透出给翻面链路
