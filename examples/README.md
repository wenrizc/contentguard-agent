# Examples

这里保存结构化输入、实际输出和脱敏 Trace。计划覆盖 `normal`、`missing_info`、`blocked`、`conflict`、`save_failure` 等场景。

离线 Trace 必须标注为流程验证；真实 DeepSeek Trace 必须标注模型、运行时间和脱敏方式。

当前已生成的 `outputs/offline-*.json` 和 `traces/offline-*.json` 是程序实际运行结果，均带有 `execution_mode=offline_mock`。其中 `offline-save-failure.json` 使用不可写数据库目录验证保存失败。Trace 中的 `return_summary` 来自本地工具，不能作为真实模型能力证明。

`outputs/real-*.json` 和 `traces/real-*.json` 是使用本地 DeepSeek 配置实际运行的脱敏结果，带有 `execution_mode=real_model`。其中冲突、确认保存和资料缺失三条路径分别展示动态调整、保存边界和阻断行为。

真实 Trace 还记录 `model`、UTC `recorded_at` 和 `redaction` 字段；其中的多 Tool Call 拒绝与重试属于真实模型运行结果。`inputs/duplicate.json` 连续运行两次后，第二次 [outputs/offline-duplicate.json](outputs/offline-duplicate.json) 与 [traces/offline-duplicate.json](traces/offline-duplicate.json) 展示幂等返回。

`test-results.txt` 保存交付时的测试、CLI 帮助和差异检查结果，并列出各验收路径对应的输入、输出和 Trace 文件。
