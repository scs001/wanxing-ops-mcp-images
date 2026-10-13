"""环境配置（家族模式：Settings.from_env，测试可注入）。

双面服务：FACET_OPS_FACE=registry（默认，/api/agents* AgentCard 面）| market
（/api/packs* 市场面）。同一镜像两个 deployment，各自基址与鉴权门探针。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    face: str = "registry"
    registry_base_url: str = "https://mcp.finddatatech.cloud"
    market_base_url: str = "https://facet.finddatatech.cloud"
    timeout_seconds: float = 15.0
    # HTTP 层鉴权门的校验缓存（token 哈希 → 判定），避免每个 initialize 都打上游
    auth_cache_ttl_seconds: float = 60.0

    @property
    def upstream_base_url(self) -> str:
        return self.market_base_url if self.face == "market" else self.registry_base_url

    @property
    def auth_probe_path(self) -> str:
        # 鉴权门轻校验端点：带 Bearer GET 一次，401=凭据失效。
        # 市场不能用 /api/packs（匿名读开着，伪 token 也 200——实测）；
        # /api/app/devices 吃 resolveUser 硬门，匿名/坏 token 皆 401（实测）。
        return "/api/app/devices" if self.face == "market" else "/api/agents?limit=1"

    @classmethod
    def from_env(cls, env=None) -> "Settings":
        env = env if env is not None else os.environ
        face = (env.get("FACET_OPS_FACE") or "registry").strip().lower()
        if face not in ("registry", "market"):
            raise ValueError(f"FACET_OPS_FACE 非法：{face!r}（registry|market）")
        return cls(
            face=face,
            registry_base_url=(
                env.get("FACET_OPS_REGISTRY_BASE_URL") or cls.registry_base_url
            ).rstrip("/"),
            market_base_url=(
                env.get("FACET_OPS_MARKET_BASE_URL") or cls.market_base_url
            ).rstrip("/"),
            timeout_seconds=float(env.get("FACET_OPS_TIMEOUT_SECONDS") or 15.0),
            auth_cache_ttl_seconds=float(env.get("FACET_OPS_AUTH_CACHE_TTL") or 60.0),
        )
