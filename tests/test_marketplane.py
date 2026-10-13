"""市场面六工具接线测试：方法/路径/参数/载荷薄转发 + 错误透传。"""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP

import facet_ops_mcp.tools_marketplane as tm
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
    monkeypatch.setattr(tm, "_current_bearer", lambda: "market-token")
    return "market-token"


async def _mk(fake):
    mcp = FastMCP("t-market")
    tm.register(mcp, fake)
    return mcp


async def test_browse_params(bearer):
    fake = FakeClient(result={"packs": []})
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        await c.call_tool("facet_market_pack_browse", {"search": "法律", "author_me": True})
    call = fake.calls[0]
    assert call["method"] == "GET" and call["path"] == "/api/packs"
    assert call["params"]["search"] == "法律"
    assert call["params"]["author"] == "me"


async def test_read_and_versions_paths(bearer):
    fake = FakeClient(result={})
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        await c.call_tool("facet_market_pack_read", {"id": "abc123"})
        await c.call_tool("facet_market_pack_versions", {"id": "abc123"})
    assert fake.calls[0]["path"] == "/api/packs/abc123"
    assert fake.calls[1]["path"] == "/api/packs/abc123/versions"


async def test_publish_thin_forward_and_packid(bearer):
    manifest = {"name": "市场助手", "manifestVersion": 1}
    fake = FakeClient(result={"id": "x1", "version": 1})
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        out = await c.call_tool(
            "facet_market_pack_publish", {"manifest": manifest, "packId": "x1"}
        )
    call = fake.calls[0]
    assert call["method"] == "POST" and call["path"] == "/api/packs"
    assert call["json_body"] == {"manifest": manifest, "packId": "x1"}  # 薄转发不改写


async def test_visibility_and_curation_writes(bearer):
    fake = FakeClient(result={"ok": True})
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        await c.call_tool("facet_market_pack_visibility", {"id": "x1", "visibility": "private"})
        await c.call_tool("facet_market_pack_curation", {"id": "x1", "category": "legal"})
    assert fake.calls[0]["json_body"] == {"visibility": "private"}
    assert fake.calls[1]["json_body"] == {"category": "legal"}


async def test_creators_gate_403_propagates(bearer):
    fake = FakeClient(error=RegistryError("forbidden", 403, "Creator group required"))
    mcp = await _mk(fake)
    async with Client(mcp) as c:
        with pytest.raises(Exception) as ei:
            await c.call_tool("facet_market_pack_publish", {"manifest": {}})
    assert "Creator group" in str(ei.value)
