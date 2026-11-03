# 评估与验证计划

## 测试分层

确定性测试覆盖规则、Mock 审核、Guardrails、SQLite 幂等、事务和失败状态。Agent 端到端测试从 CLI 入口运行，并在模型提供方边界注入离线兼容客户端。真实 DeepSeek 运行单独保存脱敏 Trace。

## 场景清单

| 编号 | 场景 | 预期 |
| --- | --- | --- |
| T01 | M01 审核通过、时段空闲 | 保存一份草稿 |
| T02 | M02 缺版权证明 | `PENDING`，不保存 |
| T03 | M03 视频高风险 | `BLOCKED`，不查排期或保存 |
| T04 | 18:00 占用、19:00 可用 | 建议 19:00，等待确认 |
| T05 | 同一请求重复提交 | 返回原草稿，不能新增 |
| T06 | SQLite 保存失败 | `save_status=FAILED` |
| T07 | 未确认替代时间 | Guardrails 拒绝保存 |
| T08 | Mock 审核超时 | `ERROR`，安全失败 |
| T09 | 工具调用达到上限 | `INCOMPLETE` |
| T10 | 修改审核资料后重跑 | 模型后续动作随工具结果改变 |

## Trace 要求

每个 Trace 都记录：输入摘要、步骤序号、工具名、脱敏参数、返回摘要、下一动作、简短决策依据、最终状态和调用次数。Trace 不记录 API Key、个人数据或模型隐藏思维过程。

## 当前状态

阶段一至五的确定性、协议和真实模型试跑均已完成。离线运行记录明确标注 `execution_mode=offline_mock`；真实模型记录标注 `execution_mode=real_model`，与离线记录分开保存。

## 已执行结果

运行命令：

```bash
uv sync
uv run pytest -q
uv run python -m src.main plan --offline --input examples/inputs/conflict.json \
  --db /tmp/contentguard-offline.sqlite \
  --trace examples/traces/offline-conflict.json
```

结果：`25 passed`。离线冲突路径返回 `NEEDS_CONFIRMATION`，审核状态为 `PASSED`，建议 `2026-11-06T19:00:00+08:00`，未保存草稿，完整结果见 [examples/outputs/offline-conflict.json](../examples/outputs/offline-conflict.json)，对应 Trace 见 [examples/traces/offline-conflict.json](../examples/traces/offline-conflict.json)。确认路径见 [offline-confirm.json](../examples/outputs/offline-confirm.json)，返回 `COMPLETED`、`SAVED`；资料缺失、规则风险、审核错误和字段不完整分别见对应的 `offline-missing.json`、`offline-rule-risk.json`、`offline-moderation-error.json` 和 `offline-incomplete-moderation.json`。

保存失败使用 `examples/fixtures/save-failure-db/` 作为不可写的数据库目录，运行结果见 [offline-save-failure.json](../examples/outputs/offline-save-failure.json)。工具返回 `save_status=FAILED`，Agent 没有报告草稿保存成功。

重复提交使用 [duplicate.json](../examples/inputs/duplicate.json) 连续运行两次，第二次结果见 [offline-duplicate.json](../examples/outputs/offline-duplicate.json)，Trace 中 `save_draft.return_summary.duplicate=true`，证明同一业务键只返回原草稿。

离线记录只证明工具协议、状态和边界流程，不能证明真实模型会作出相同决策。

真实模型运行命令与结果：

```bash
uv run python -m src.main plan --input examples/inputs/conflict.json \
  --db /tmp/contentguard-real-conflict.sqlite \
  --trace examples/traces/real-conflict.json
uv run python -m src.main confirm --input examples/inputs/conflict.json \
  --agreed-time 2026-11-06T19:00:00+08:00 \
  --db /tmp/contentguard-real-confirm.sqlite \
  --trace examples/traces/real-confirm.json
uv run python -m src.main plan --input examples/inputs/missing-info.json \
  --db /tmp/contentguard-real-missing.sqlite \
  --trace examples/traces/real-missing-info.json
```

实际结果：冲突路径为 `NEEDS_CONFIRMATION`，确认路径为 `COMPLETED/SAVED/CONFIRMED`，缺版权资料路径为 `BLOCKED/PENDING`。结果和 Trace 分别见 `examples/outputs/real-*.json` 与 `examples/traces/real-*.json`。每份真实 Trace 均标注 `model`、UTC `recorded_at` 和脱敏说明。运行期间没有把 API Key 写入输出；多 Tool Call 被边界拒绝后模型重试成功，累计调用次数仍低于 10 次上限。

## 已知限制与未完成部分

- 视频审核仍是标注为 `mock` 的合成结果，不能证明真实画面或音频识别效果。
- V1 每次处理一个素材，只保存排期草稿，不执行正式发布。
- 尚未接入生产身份权限、数据库迁移、并发压测和真实审核供应商；这些属于生产化工作，不是本题 V1 验收范围。
