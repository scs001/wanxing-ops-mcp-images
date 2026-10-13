"""环境配置（家族模式：Settings.from_env，测试可注入）。"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    registry_base_url: str = "https://mcp.finddatatech.cloud"
    timeout_seconds: float = 15.0
    # HTTP 层鉴权门的校验缓存（token 哈希 → 判定），避免每个 initialize 都打 registry
    auth_cache_ttl_seconds: float = 60.0

    @classmethod
    def from_env(cls, env=None) -> "Settings":
        env = env if env is not None else os.environ
        return cls(
            registry_base_url=(
                env.get("FACET_OPS_REGISTRY_BASE_URL") or cls.registry_base_url
            ).rstrip("/"),
            timeout_seconds=float(env.get("FACET_OPS_TIMEOUT_SECONDS") or 15.0),
            auth_cache_ttl_seconds=float(env.get("FACET_OPS_AUTH_CACHE_TTL") or 60.0),
        )
