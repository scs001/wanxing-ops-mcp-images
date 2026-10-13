# facet-ops-mcp image — 谦面（facet 线）市场操作 MCP。
#
# 发布通道：GitHub Actions -> TCR（家族配方 docs/IMAGE-RELEASE.md 六步清单）。
# 上游源为默认（美国 runner 绕道国内镜像会把构建拖成小时级），国内镜像源一律 ARG 且默认空；单层 <300MB。
FROM python:3.12-slim

ARG PIP_INDEX_URL=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY facet_ops_mcp ./facet_ops_mcp

RUN if [ -n "$PIP_INDEX_URL" ]; then pip install --no-cache-dir -i "$PIP_INDEX_URL" .; else pip install --no-cache-dir .; fi \
 && useradd -m -u 1000 appuser

USER appuser

EXPOSE 8000

CMD ["facet-ops-mcp", "serve", "--host", "0.0.0.0", "--port", "8000"]
