# Data

只存放合成素材、规则、授权和排期数据。不得提交真实用户视频、真实版权凭证或隐私信息。

## 文件格式

- `materials.json`：`materials` 数组，每项用 `material_id` 关联素材元数据、字幕和版权引用。
- `authorizations.json`：`copyright_authorizations` 数组，每项记录素材、目标平台、有效期和授权状态；缺少项表示资料不足。
- `review_rules.json`：`rules` 数组，记录规则 ID、类别、严重级别和处置动作。`match_terms` 是合成测试规则数据，供后续确定性规则工具读取。
- `moderation_mock.json`：`results` 数组，模拟外部视频审核服务。`provider` 固定为 `mock`，证据来源带有 `simulated_` 的结果不能解释为真实视频识别。
- `schedules.json`：`slots` 数组，记录已有账号排期。时间使用 ISO 8601 并带时区；`start` 与 `end` 是半开时间区间。

任务输入放在 `examples/inputs/`，至少包含 `source_request_id`、`material_ids`、`account_id`、`platform`、`requested_start`、`duration_minutes`、`hard_time` 和 `conflict_policy`。
