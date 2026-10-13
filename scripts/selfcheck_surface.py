#!/usr/bin/env python3
"""tool-surface manifest 双向 selfcheck（mcp-surface-contract）——双面。

对每个面（registry→tool-surface.json / market→tool-surface.market.json）断言：
  1. 一致：manifest 声明的工具 == 该面运行时注册的工具（create_server(face=...)）
  2. 闭合：任何消费侧暴露的工具集 ⊆ 对应 manifest 的 commercial 集
     ——消费侧由 --consumers 传入的 pack/套件目录提供

用法：
    python3 scripts/selfcheck_surface.py                    # 只做方向 1（双面）
    python3 scripts/selfcheck_surface.py --consumers <dir>  # 加方向 2
退出码：0 通过 / 1 失败（列出差异）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FACES = {
    "registry": {"manifest": REPO / "tool-surface.json", "server": "facet-ops-mcp"},
    "market": {"manifest": REPO / "tool-surface.market.json", "server": "facet-market-mcp"},
}


def fail(problems: list[str]) -> None:
    print("SELFCHECK FAIL:")
    for p in problems:
        print(f"  - {p}")
    sys.exit(1)


def load_manifest(path: Path) -> dict:
    if not path.exists():
        fail([f"manifest 缺失：{path}（契约：缺失即未上牌）"])
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_tools(m: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for g in m.get("tool_groups", []):
        level = g.get("level")
        if level not in ("commercial", "internal"):
            fail([f"tool_groups.{g.get('group')} 的 level 非法：{level!r}"])
        for t in g.get("tools", []):
            if t in out and out[t] != level:
                fail([f"工具 {t} 在多个 group 中级别冲突"])
            out[t] = level
    return out


async def runtime_tools(face: str) -> set[str]:
    sys.path.insert(0, str(REPO))
    try:
        from facet_ops_mcp.config import Settings
        from facet_ops_mcp.server import create_server

        mcp = create_server(Settings(face=face))
        return {t.name for t in await mcp.list_tools()}
    except Exception as e:
        fail([f"[{face}] 运行时工具面获取失败：{e!r}"])


def consumer_tools(path: Path, servers: set[str]) -> dict[str, set[str]]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, set[str]] = {}
    for srv in servers:
        pattern = re.compile(rf"mcp__{re.escape(srv)}__([A-Za-z0-9_.\-]+)")
        found = set(pattern.findall(text))
        if found:
            out.setdefault(srv, set()).update(found)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--consumers", nargs="*", default=[])
    args = parser.parse_args()

    problems: list[str] = []
    all_commercial: dict[str, set[str]] = {}
    total = 0
    for face, spec in FACES.items():
        m = load_manifest(spec["manifest"])
        levels = manifest_tools(m)
        declared = set(levels)
        runtime = asyncio.run(runtime_tools(face))
        total += len(runtime)
        if declared != runtime:
            only_manifest = sorted(declared - runtime)
            only_runtime = sorted(runtime - declared)
            if only_manifest:
                problems.append(f"[{face}] manifest 多声明（代码未注册）：{only_manifest}")
            if only_runtime:
                problems.append(f"[{face}] 代码多注册（manifest 未声明）：{only_runtime}")
        all_commercial[spec["server"]] = {
            t for t, lv in levels.items() if lv == "commercial"
        }

    for c in args.consumers:
        cpath = Path(c)
        files = [cpath] if cpath.is_file() else sorted(cpath.rglob("*")) if cpath.is_dir() else []
        for f in files:
            if not f.is_file() or f.suffix not in (".json", ".md", ".yaml", ".yml"):
                continue
            try:
                exposed = consumer_tools(f, set(all_commercial))
            except Exception:
                continue
            for srv, tools in exposed.items():
                overflow = tools - all_commercial[srv]
                if overflow:
                    problems.append(f"消费侧 {f} 对 {srv} 暴露非 commercial 工具：{sorted(overflow)}")

    if problems:
        fail(problems)
    faces = "+".join(FACES)
    print(f"SELFCHECK PASS: {faces} 共 {total} tools，manifest↔runtime 一致" +
          (f"，{len(args.consumers)} 消费侧闭合" if args.consumers else ""))


if __name__ == "__main__":
    main()
