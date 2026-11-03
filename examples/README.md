# Examples

这里保存结构化输入、实际输出和脱敏 Trace。计划覆盖 `normal`、`missing_info`、`blocked`、`conflict`、`save_failure` 等场景。

离线 Trace 必须标注为流程验证；真实 DeepSeek Trace 必须标注模型、运行时间和脱敏方式。

当前已生成的 `outputs/offline-*.json` 和 `traces/offline-*.json` 是程序实际运行结果，均带有 `execution_mode=offline_mock`。其中 `offline-save-failure.json` 使用不可写数据库目录验证保存失败。Trace 中的 `return_summary` 来自本地工具，不能作为真实模型能力证明。
