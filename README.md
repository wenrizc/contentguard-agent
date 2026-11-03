# ContentGuard Agent

基于证据审核、安全约束与动态排期的 ReAct Agent，面向小影（VivaVideo）内容运营场景。

当前仓库处于设计与工程骨架阶段。目标是让 Agent 读取合成短视频素材、版权与审核资料，使用 DeepSeek 的 Tool Calling 根据工具结果动态选择下一步，并只保存可确认的排期草稿，不执行真实发布。

## 当前设计

- **真实模型决策**：默认通过 OpenAI 兼容 SDK 调用 DeepSeek。
- **Mock 外部审核**：视频画面/音频审核使用合成 Mock 结果；规则、排期和 SQLite 保存由本项目真实执行。
- **ReAct 循环**：模型每轮选择一个工具，观察结构化结果，再决定继续检查、寻找时段、请求确认、阻断或结束。
- **安全边界**：审核未通过、审核结果缺失、硬性时间未确认和保存失败都不能被报告为成功。
- **离线入口**：离线模型只验证流程与工具协议，不证明真实模型的决策效果。

## 计划中的运行方式

```bash
python -m src.main plan --input examples/inputs/conflict.json
python -m src.main confirm --input examples/inputs/conflict.json \
  --agreed-time 2026-11-06T19:00:00+08:00
python -m src.main plan --input examples/inputs/missing-info.json --offline
```

## 环境

```bash
uv sync
uv run python -m src.main --help
cp .env.example .env
```

项目使用 `uv` 统一管理 Python 版本约束、依赖和锁文件，不维护 `requirements.txt`。默认使用清华 PyPI 镜像，开发和测试命令统一通过 `uv run` 执行。

真实模型运行需要自行配置 DeepSeek API Key。禁止把真实密钥提交到仓库。

## 仓库入口

- [AGENTS.md](AGENTS.md)：后续开发和 AI 协作规范。
- [docs/01-requirements.md](docs/01-requirements.md)：用户、目标和验收标准。
- [docs/02-solution.md](docs/02-solution.md)：ReAct、工具边界、数据流和技术取舍。
- [docs/03-evaluation.md](docs/03-evaluation.md)：测试计划、Trace 规范和已知限制。
- [docs/04-ai-usage.md](docs/04-ai-usage.md)：AI 辅助范围、个人修改和验证记录。
- [docs/05-retrospective.md](docs/05-retrospective.md)：开发复盘，完成后补充。
- [docs/06-implementation-plan.md](docs/06-implementation-plan.md)：分阶段实施计划。

## 项目状态

当前提交只建立设计基线和目录结构，尚未声称核心 Agent、工具和测试已经完成。后续实现必须同步更新评估文档和实际运行记录。
