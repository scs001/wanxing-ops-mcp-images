# facet-ops-mcp — 谦面操作 MCP（双面）

同一镜像两个 deployment（`FACET_OPS_FACE` 切脸）：

| 脸 | 服务 | 上游面 | 凭据（壹座 ref） |
|---|---|---|---|
| registry（默认） | facet-ops-mcp（:31892） | registry 网关 AgentCard `/api/agents*` | `registry`（既有） |
| market | facet-market-mcp（:31893） | facet 市场 `/api/packs*` | `facet-market`（C1.1-B：Ed25519 设备密钥+静默挑战续登） |

五线 AI 操作面 C1/C1.1 切片：registry 面=AgentCard 目录操作；market 面=**发布 pack 到谦面市场**（头牌）+浏览/版本/可见性/策展。

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
| `facet_agent_read` | GET `/api/agents/{path}` | |
| `facet_agent_publish` | POST `/api/agents/register`（AgentCard 登记） | ✅ |
| `facet_agent_update` | PUT `/api/agents/{path}` | ✅ |
| `facet_agent_toggle` | POST `/api/agents/{path}/toggle` | ✅ |
| `facet_agent_duplicate_check` | POST `/api/agents/check-duplicates`（恒 200） | |

## 环境

| 变量 | 默认 | 说明 |
|---|---|---|
| `FACET_OPS_FACE` | `registry` | `registry` \| `market` 切脸 |
| `FACET_OPS_REGISTRY_BASE_URL` | `https://mcp.finddatatech.cloud` | registry 网关基址 |
| `FACET_OPS_MARKET_BASE_URL` | `https://facet.finddatatech.cloud` | facet 市场基址 |
| `FACET_OPS_TIMEOUT_SECONDS` | `15` | 上游超时 |
| `FACET_OPS_AUTH_CACHE_TTL` | `60` | 鉴权门校验缓存 TTL（秒） |

## 本地

```bash
pip install -e ".[dev]"
pytest                                # 测试
python3 scripts/selfcheck_surface.py  # 双面上牌 selfcheck（12 工具）
facet-ops-mcp serve --port 8000       # /health 无门；/mcp 带鉴权门
```
