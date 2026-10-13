"""CLI 入口：serve（uvicorn 跑完整 ASGI 应用）。"""

from __future__ import annotations

import click
import uvicorn


@click.group()
@click.version_option(package_name="facet-ops-mcp")
def cli() -> None:
    """facet-ops-mcp — 谦面市场操作 MCP。"""


@cli.command()
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
def serve(host: str, port: int) -> None:
    from .server import build_app

    uvicorn.run(build_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    cli()
