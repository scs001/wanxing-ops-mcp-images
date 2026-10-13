# facet-ops-mcp — 谦面市场操作 MCP

谦面（facet 线）的动作 MCP（五线 AI 操作面 C1 切片）：把 registry console API 的
pack 操作面暴露给 AI agent——**浏览目录、读详情、发布、更新、上下架、发布前查重**。

- 契约：`openspec/changes/facet-ops-mcp/specs/facet-ops-mcp/spec.md`（finddata 工作区）
- 接入规约：`LINES-MCP-CONFORMANCE.md`（五线对齐清单）
- 决策出处：paas `docs/yizuo-platform-roadmap.md`「AI 操作面」节

## 身份模型（用户委托）

每个工具调用从进站 MCP 请求取 `Authorization` 原样转发给 registry——以**调用方用户身份**
执行，可见域与写权限由 registry 判定。本服务不落任何凭据；HTTP 层鉴权门：
匿名 POST `/mcp` → 401；registry 判 401 → 401（壹座 preflight 探针可见 auth-rejected）；
registry 不可达 → 放行（工具层诚实报 unreachable）。

## 工具面（六工具，全 commercial）

| 工具 | registry 端点 | 写 |
|---|---|---|
| `facet_catalog_browse` | GET `/api/agents` | |
| `facet_pack_read` | GET `/api/agents/{path}` | |
| `facet_pack_publish` | POST `/api/agents/register` | ✅ |
| `facet_pack_update` | PUT `/api/agents/{path}` | ✅ |
| `facet_pack_toggle` | POST `/api/agents/{path}/toggle` | ✅ |
| `facet_duplicate_check` | POST `/api/agents/check-duplicates`（恒 200） | |

## 环境

| 变量 | 默认 | 说明 |
|---|---|---|
| `FACET_OPS_REGISTRY_BASE_URL` | `https://mcp.finddatatech.cloud` | registry console API 基址 |
| `FACET_OPS_TIMEOUT_SECONDS` | `15` | 上游超时 |
| `FACET_OPS_AUTH_CACHE_TTL` | `60` | 鉴权门校验缓存 TTL（秒） |

## 本地

```bash
pip install -e ".[dev]"
pytest                                # 测试
python3 scripts/selfcheck_surface.py  # 上牌 selfcheck（manifest↔运行时一致）
facet-ops-mcp serve --port 8000       # /health 无门；/mcp 带鉴权门
```
