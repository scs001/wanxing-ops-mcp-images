"""环境配置（家族模式：Settings.from_env，测试可注入）。"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # 萬星独立面（unify-wanxing-a2a-face 3.x 迁址）：管理半边自 paas 网关摘挂后，
    # console 编址路由只存在于萬星 facade——base URL 指向 wanxing 域。
    base_url: str = "https://wanxing.finddatatech.cloud"
    timeout_seconds: float = 15.0
    auth_cache_ttl_seconds: float = 60.0

    @classmethod
    def from_env(cls, env=None) -> "Settings":
        env = env if env is not None else os.environ
        return cls(
            base_url=(env.get("WANXING_OPS_BASE_URL") or cls.base_url).rstrip("/"),
            timeout_seconds=float(env.get("WANXING_OPS_TIMEOUT_SECONDS") or 15.0),
            auth_cache_ttl_seconds=float(env.get("WANXING_OPS_AUTH_CACHE_TTL") or 60.0),
        )
