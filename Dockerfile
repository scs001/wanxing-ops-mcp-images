# wanxing-ops-mcp image — 萬星（wanxing 线）舰队操作 MCP。
#
# 发布通道：GitHub Actions -> TCR（家族配方 docs/IMAGE-RELEASE.md；镜像仓
# law-ai-official/facet-ops-mcp-images 增线）。上游源为默认；单层 <300MB。
FROM python:3.12-slim

ARG PIP_INDEX_URL=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY wanxing_ops_mcp ./wanxing_ops_mcp

RUN if [ -n "$PIP_INDEX_URL" ]; then pip install --no-cache-dir -i "$PIP_INDEX_URL" .; else pip install --no-cache-dir .; fi \
 && useradd -m -u 1000 appuser

USER appuser

EXPOSE 8000

CMD ["wanxing-ops-mcp", "serve", "--host", "0.0.0.0", "--port", "8000"]
