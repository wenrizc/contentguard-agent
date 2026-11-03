# AI 辅助使用记录

## AI 辅助范围

- 讨论小影短视频审核、版权资料、账号排期和“只保存草稿”的业务边界，并比较 LangGraph、AgentScope、smolagents 与原生 Tool Calling 的取舍。
- 辅助生成数据模型、确定性工具、SQLite 事务、ReAct Runner、CLI 和测试的初稿。
- 辅助组织 README、需求、方案、评估、实施计划和复盘文档。

## 个人修改与审核

- 人工确认六个合成素材场景、时间冲突规则、状态拆分、用户确认边界和幂等键。
- 删除会替模型决定下一步的固定流水线；保留模型选择工具、工具结果回填和 `finish` 结构化结束动作。
- 增加保存前 Guardrails、SQLite 事务内冲突复核、UTC 时间规范化、保存失败结构化返回和 Trace 脱敏边界。
- 对每个阶段执行 `uv run pytest -q`、CLI 帮助检查和 `git diff --check`；离线运行记录由程序生成并标注 `offline_mock`。

## 验证边界

本仓库没有提交真实密钥。真实试跑使用本地 `.env` 的 `LLM_API_KEY`，接入只通过 `OpenAIChatClient`；输出经过检查未包含密钥，真实结果保存为 `examples/outputs/real-*.json` 和 `examples/traces/real-*.json`。离线假客户端结果仍只证明流程，不能替代真实模型决策效果。

## 凭据与隐私

API Key 只放在本地 `.env`，不提交到 Git。样例素材和授权资料均为合成数据。
