# 分阶段实施计划

本计划从当前设计基线开始执行。每个阶段都有可检查的产物；完成一个阶段后再进入下一个阶段，避免先堆积框架代码再验证核心链路。

## 阶段一：环境与数据基线（已完成）

建立 `uv` 环境，使用 `pyproject.toml` 管理运行依赖和开发依赖，默认从清华 PyPI 镜像解析依赖，生成并提交 `uv.lock`。确认 CLI 模块可以启动。

准备合成数据：

- M01：审核通过，目标时段冲突，存在可用候选时段。
- M02：缺少版权证明。
- M03：Mock 视频审核返回高风险。
- M04：字幕命中夸大宣传规则。
- M05：Mock 审核服务错误。
- M06：审核结果字段不完整。

阶段完成条件：任务输入、素材档案、规则、授权和已有排期都有明确 JSON 格式，且不包含真实用户数据。

已交付：`data/*.json` 合成资料、`examples/inputs/*.json` 输入样例、`src/main.py` CLI 启动入口及 `tests/test_baseline.py` 基线测试。验证命令和结果记录在阶段提交中。

## 阶段二：确定性业务工具（已完成）

实现素材读取、规则检查、Mock 视频审核、指定时段查询、候选时段查询和 SQLite 草稿保存。

先验证业务事实，再接入模型：审核结果必须包含状态、规则 ID、严重级别和证据来源；模拟视频证据必须明确标注为合成结果。

阶段完成条件：可以独立验证资料缺失、规则风险、审核错误、时间冲突、重复提交和保存失败。

已交付：Pydantic 数据契约、素材读取、规则聚合、Mock 视频审核、排期查询和 SQLite 草稿存储；`tests/test_tools.py` 覆盖上述状态与失败场景。下一阶段只在这些接口上增加保存安全边界和事务内复核。

## 阶段三：保存与安全边界（已完成）

实现 Guardrails 和事务保存：

- 审核未通过时禁止保存。
- 未经用户确认不能保存替代时段。
- 保存前重新检查时段，处理确认后的并发占用。
- 使用 `source_request_id + material_id + account_id + start` 实现幂等。
- 保存失败返回明确失败状态。

阶段完成条件：安全约束能够拒绝越权保存，并返回违反的具体规则；安全层不替模型选择后续工具。

已交付：`src/guardrails.py` 拒绝未通过审核、未确认的替代时段和无时区时间；`DraftStore` 在事务内复核已有排期与已保存草稿，并使用 UTC 规范化时间。`tests/test_guardrails.py` 覆盖越权拒绝、显式确认、时区校验和并发冲突。

## 阶段四：真实 ReAct Agent（已完成）

使用 OpenAI SDK 的兼容 Tool Calling 接入 DeepSeek。AgentRunner 每轮最多执行一个工具调用，收到工具结果后再请求模型决定下一步；最大工具调用次数为 10。

实现 `finish` 结构化结束动作，支持 `COMPLETED`、`NEEDS_CONFIRMATION`、`BLOCKED`、`INCOMPLETE` 等任务状态。工具异常、模型无效参数和步数耗尽都要写入 Trace。

阶段完成条件：M01 能走完“审核通过 → 发现冲突 → 查询候选 → 请求确认”；确认后能重新核验并保存草稿。M03 或 M05 能根据工具结果停止排期。

已交付：`src/llm_client.py` 的 DeepSeek 兼容客户端、`src/agent.py` 的单工具 ReAct 循环、结构化 `finish`、Trace 和 10 次调用上限，以及 `src/main.py` 的 `plan`/`confirm` CLI 入口。`tests/test_agent.py` 用协议边界假客户端验证冲突改走候选、风险阻断和审核通过后保存；这些测试不代表真实模型决策质量。

## 阶段五：离线测试与真实 Trace（离线部分已完成）

通过模型客户端边界注入离线假模型，只验证工具协议、循环、Guardrails 和状态结果。离线结果必须标明不能证明真实模型决策质量。

配置 DeepSeek 后录制脱敏真实 Trace，至少包含：

- 审核通过但时间冲突，模型选择查询候选并请求确认。
- 规则风险或审核错误，模型阻断后续排期。

Trace 保存步骤、工具参数、返回摘要、下一动作和简短决策依据，不保存 API Key 或隐藏思维过程。

已交付离线部分：`src/offline.py` 根据上一次工具返回结果选择下一步，CLI 的 `--offline --trace` 可生成带 `execution_mode=offline_mock` 的流程记录。真实 DeepSeek Trace 仍需在配置凭据后录制；当前环境没有配置 `LLM_API_KEY`，离线结果不能证明模型决策质量。

## 阶段六：文档与交付验证

完成 README、需求、方案、评估、AI 使用和复盘文档。`docs/03-evaluation.md` 引用 examples 下的实际输入、输出和 Trace，区分确定性测试、离线测试和真实模型验证。

交付前执行：

```bash
uv sync
uv run pytest
uv run python -m src.main --help
git diff --check
git status --short
```

交付内容必须包含可复制运行命令、环境变量说明、最终 commit SHA、已知限制和未完成部分。
