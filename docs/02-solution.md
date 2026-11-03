# 方案设计

## 架构

```text
CLI
  -> AgentRunner
       -> DeepSeek Tool Calling
       -> get_material
       -> check_rules (规则 + Mock 视频审核)
       -> check_slot / find_slots
       -> save_draft
       -> finish
  -> 结构化结果 + Trace
```

AgentRunner 每轮把模型选择的一个工具调用发送到本地工具，工具结果以结构化 `tool` 消息回填给模型。Runner 设置最大 10 次工具调用；超限返回 `INCOMPLETE`。

## 工具职责

- `get_material` 只读取素材档案和证据引用，不判定审核通过。
- `check_rules` 聚合元数据、授权、字幕规则、品牌规则和 Mock 视频审核结果，返回规则 ID、证据来源、严重级别和处置建议。
- `check_slot` 只检查指定时段。
- `find_slots` 只查找候选时段；返回候选不等于用户批准。
- `save_draft` 在 SQLite 事务内重新检查审核资格、授权时间和排期冲突，并依据唯一业务键幂等写入。
- `finish` 将模型的结构化结论交给结果校验，不把模型结论改写成另一种状态。

阶段二已经落地的确定性实现位于 `src/tools/`、`src/moderation/` 和 `src/storage.py`：

- `MaterialTool.get_material` 返回 `FOUND` 或 `NOT_FOUND`，并显式返回授权资料是否存在。
- `ReviewTool.check_rules` 返回 `PASSED`、`PENDING`、`BLOCKED`、`UNKNOWN` 或 `ERROR`，每个风险包含规则 ID、严重级别、原因和证据来源。
- `ScheduleTool.check_slot` 返回指定区间的冲突项；`find_slots` 只返回按小时网格计算出的候选，不代表用户确认。
- `DraftStore.save_draft` 使用 SQLite 业务唯一键实现重复提交幂等，并把数据库错误返回为 `FAILED`。

这些工具目前可在没有模型的情况下直接测试。阶段三的 `Guardrails` 只负责审核资格、确认权限和时区约束；`DraftStore` 在 `BEGIN IMMEDIATE` 事务中复核占用区间，并在成功写入时登记 `DRAFT` 占用，避免确认后并发抢占。

## Guardrails

Guardrails 是副作用边界，不是隐藏的业务决策器。它可以拒绝：审核未通过时保存、未确认的替代时间保存、格式无效的时间、重复或冲突的写入。拒绝信息必须指出违反的规则，并将结果返回模型。

## 视频审核适配

V1 定义 `VideoModerator` 协议并实现 `MockVideoModerator`。Mock 数据覆盖通过、缺资料、高风险、服务错误和字段不完整。返回中必须包含 `provider=mock` 与 `evidence_source=simulated_video_frame`。

未来可以增加 Sightengine 适配器，将外部结果转换成相同标准格式；V1 不配置、不调用其 API，也不保留未使用的生产分支。

## 状态与幂等

结果分为 `review_status`、`task_status`、`save_status`、`confirmation_status` 四类。草稿唯一键为 `source_request_id + material_id + account_id + start`。保存时使用事务并再次核验时段，避免确认后发生并发占用。

## 技术取舍与参考

使用原生 Python、OpenAI SDK、Pydantic、SQLite 和 pytest。LangGraph、AgentScope 和 smolagents 可作为架构参考，但本项目不引入框架运行时，避免把单一 ReAct 循环包装成固定状态图。

参考：

- https://github.com/langchain-ai/langgraph
- https://github.com/agentscope-ai/agentscope
- https://github.com/huggingface/smolagents
- https://github.com/openai/openai-cookbook
- https://github.com/deepseek-ai/DeepSeek-V3

实现阶段应记录实际查看的 README、示例路径和版本。若开发环境仍无法访问 GitHub，应在评估文档中如实记录，不声称完成逐仓库验证。
