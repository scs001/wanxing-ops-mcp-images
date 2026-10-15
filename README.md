# wanxing-ops-mcp — 萬星舰队操作 MCP

萬星（wanxing 线）的动作 MCP（五线 AI 操作面 C2 切片）：把 agent 服务的公开目录、
AgentCard、部署者允许清单、启停与 A2A 回合暴露给 AI agent。

- 契约：`openspec/changes/wanxing-ops-mcp/specs/wanxing-ops-mcp/spec.md`（finddata 工作区）
- 接入规约：`LINES-MCP-CONFORMANCE.md`；serving API 一页纸：paas `docs/wanxing-serving-api.md`

## 双凭据分型（身份模型定案）

| 型 | 工具 | 凭据 |
|---|---|---|
| 调用型（管理面） | browse/card/callers*/pause/resume | 壹座平台令牌（用户委托） |
| 对话型 | `wanxing_agent_turn` | caller `sk-`（计费面板自铸；边界结算） |

**回执≠结果**：turn 的同步应答是 agent 的即时答复；工单型 agent 的查询约定（SUBMIT/STATUS）
在各 agent 的 AgentCard/技能文档里。

## 工具面（7 调用型 commercial + 1 对话型 internal）

| 工具 | 端点 | 写 |
|---|---|---|
| `wanxing_agents_browse` | GET `/api/wanxing/v1/agents`（公开） | |
| `wanxing_agent_card` | GET `/api/wanxing/v1/a2a/{slug}/.well-known/agent-card.json`（公开） | |
| `wanxing_callers_list` | GET `/api/packs/{id}/deployments/{agent}/callers` | |
| `wanxing_callers_add` | POST 同上 {email} | ✅ |
| `wanxing_callers_remove` | DELETE 同上 {userId} | ✅ |
| `wanxing_agent_pause` / `wanxing_agent_resume` | POST .../pause\|resume | ✅ |
| `wanxing_agent_turn` | POST `/api/wanxing/v1/a2a/{slug}`（message/send + Idempotency-Key） | 计费 |

## 环境

| 变量 | 默认 | 说明 |
|---|---|---|
| `WANXING_OPS_BASE_URL` | `https://platform.finddatatech.cloud` | 萬星对客面基址 |
| `WANXING_OPS_TIMEOUT_SECONDS` | `15` | 上游超时 |
| `WANXING_OPS_AUTH_CACHE_TTL` | `60` | 鉴权门缓存 TTL（秒） |

## 本地

```bash
pip install -e ".[dev]"
pytest                                # 测试
python3 scripts/selfcheck_surface.py  # 上牌 selfcheck
wanxing-ops-mcp serve --port 8000     # /health 无门；/mcp 无 Bearer 401
```
