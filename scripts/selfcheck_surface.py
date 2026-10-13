#!/usr/bin/env python3
"""tool-surface manifest 双向 selfcheck（mcp-surface-contract）。

断言两个方向：
  1. 一致：manifest 声明的工具 == 代码注册的工具（运行时真值 `mcp.list_tools()`）
  2. 闭合：任何消费侧暴露的工具集 ⊆ manifest 的 commercial 集
     ——消费侧由 --consumers 传入的 pack/套件目录提供

用法：
    python3 scripts/selfcheck_surface.py                    # 只做方向 1
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
MANIFEST = REPO / "tool-surface.json"
SERVER_NAME = "facet-ops-mcp"

TOOL_PATTERN = re.compile(rf"mcp__{re.escape(SERVER_NAME)}__([A-Za-z0-9_.\-]+)")


def fail(problems: list[str]) -> "None":
    print("SELFCHECK FAIL:")
    for p in problems:
        print(f"  - {p}")
    sys.exit(1)


def load_manifest() -> dict:
    if not MANIFEST.exists():
        fail([f"manifest 缺失：{MANIFEST}（契约：缺失即未上牌）"])
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


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


async def runtime_tools() -> set[str]:
    sys.path.insert(0, str(REPO))
    try:
        from facet_ops_mcp.server import create_server

        mcp = create_server()
        return {t.name for t in await mcp.list_tools()}
    except Exception as e:  # 导入失败也如实失败，不回退猜测
        fail([f"运行时工具面获取失败：{e!r}"])


def consumer_tools(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(TOOL_PATTERN.findall(text))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--consumers", nargs="*", default=[])
    args = parser.parse_args()

    m = load_manifest()
    levels = manifest_tools(m)
    declared = set(levels)
    runtime = asyncio.run(runtime_tools())

    problems: list[str] = []
    if declared != runtime:
        only_manifest = sorted(declared - runtime)
        only_runtime = sorted(runtime - declared)
        if only_manifest:
            problems.append(f"manifest 多声明（代码未注册）：{only_manifest}")
        if only_runtime:
            problems.append(f"代码多注册（manifest 未声明）：{only_runtime}")

    commercial = {t for t, lv in levels.items() if lv == "commercial"}
    for c in args.consumers:
        cpath = Path(c)
        files = [cpath] if cpath.is_file() else sorted(cpath.rglob("*")) if cpath.is_dir() else []
        for f in files:
            if not f.is_file() or f.suffix not in (".json", ".md", ".yaml", ".yml"):
                continue
            exposed = consumer_tools(f)
            overflow = exposed - commercial
            if overflow:
                problems.append(f"消费侧 {f} 暴露非 commercial 工具：{sorted(overflow)}")

    if problems:
        fail(problems)
    print(f"SELFCHECK PASS: {len(runtime)} tools, manifest↔runtime 一致" +
          (f"，{len(args.consumers)} 消费侧闭合" if args.consumers else ""))


if __name__ == "__main__":
    main()
