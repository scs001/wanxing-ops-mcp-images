"""AuthGate 判定语义：匿名拒、401 透传、不可达放行、缓存生效。"""

from __future__ import annotations

from facet_ops_mcp.auth_gate import AuthGate
from facet_ops_mcp.client import RegistryClient, RegistryError


class ExplodingClient:
    def __init__(self, error=None):
        self.error = error
        self.calls = 0

    async def request(self, method, path, *, bearer, params=None, json_body=None):
        self.calls += 1
        if self.error:
            raise self.error
        return {"agents": []}


async def test_anonymous_rejected():
    gate = AuthGate(ExplodingClient())
    assert await gate.check(None) is False


async def test_valid_token_passes():
    c = ExplodingClient()
    gate = AuthGate(c, ttl_seconds=60)
    assert await gate.check("tok") is True
    assert c.calls == 1


async def test_registry_401_rejects():
    gate = AuthGate(ExplodingClient(RegistryError("unauthorized", 401, "expired")))
    assert await gate.check("tok") is False


async def test_registry_unreachable_passes_through():
    gate = AuthGate(ExplodingClient(RegistryError("unreachable", None, "refused")))
    assert await gate.check("tok") is True


async def test_cache_short_circuits():
    c = ExplodingClient()
    gate = AuthGate(c, ttl_seconds=60)
    await gate.check("tok")
    await gate.check("tok")
    assert c.calls == 1  # 第二次走缓存
