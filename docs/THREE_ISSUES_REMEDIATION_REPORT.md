# 三项考核反馈第二阶段修复报告

## 1. 本次发现的问题

独立审计发现两项 PARTIAL 风险：

1. src/vlm_pipeline.py 的 ggregate_objects 接受字符串物品并自动补 count=1，导致 {"objects":["mouse"]} 可以进入正常统计。
2. src/comparison.py 主要依据 rror 和 untime_seconds 判断 verified，没有复用生产 Schema 校验，缺少独立防线。

数量累加和统一重试在上一轮审计中为 PASS，本次保留原有实现并补充了 RANDOM_123 测试。

## 2. 修改文件与函数

- src/vlm_pipeline.py
  - 修改 ggregate_objects
  - 新增 alidate_result_record
  - 在 un_vlm 成功保存前调用统一结果校验
  - 为成功与失败结果补充 done 字段
- src/comparison.py
  - compare_row 复用 alidate_result_record
  - 只有完整合法的 VLM 结果才进入 verified 和正常 lm_counts
  - 非法结果统一输出 error 状态和空统计
  - 修复 JSON 文件写入的文件句柄关闭问题
- 	ests/test_vlm_pipeline.py
  - 增加 Schema、comparison、完整模拟生产流程和三种 ID 独立性测试
- docs/THREE_ISSUES_REMEDIATION_REPORT.md
  - 本报告

原有独立审计报告 docs/THREE_ISSUES_CODE_AUDIT.md 未覆盖或修改。

## 3. 具体修复内容

ggregate_objects 现在只接受字典形式的物品记录。每条记录必须有非空 
ame 和正整数 count。字符串物品、缺少字段、空名称、负数、零、浮点数、字符串数量和布尔数量都会被拒绝。中文英文映射和同类累加逻辑保留。

新增 alidate_result_record 作为统一保存结果校验入口。它检查结果字段、method、image_id、objects、counts、done、done_reason、rror 和尝试记录，并重新聚合 objects 验证 counts 一致性。

comparison.py 在生成 verified 前再次调用同一个校验函数。上游结果即使没有 error 且有 runtime_seconds，只要缺少验证元数据、对象 Schema 非法、done 不完整、统计不一致，就会被标记为 error。

合法的 {"objects":[]} 在 done=true、done_reason=stop、error 为 null 且尝试记录完整时可以 verified。

## 4. 新增测试

- 	est_invalid_values
  - 字符串数组
  - 缺少 name
  - 缺少 count
  - 空 name
  - count 为 true、负数、浮点数、字符串
  - 空响应、空 JSON、objects=null、objects 非数组
- 	est_comparison_requires_verified_record
  - 非法 VLM 结果即使有 runtime_seconds 且 error 为空，也不能 verified
- 	est_comparison_accepts_complete_empty_result_and_writes_consistent_files
  - 合法空数组可以 verified
  - comparison.json 与 comparison.csv 状态一致
- 	est_mocked_production_flow_rejects_invalid_objects_before_comparison
  - 调用真实 un_vlm 和 compare_row，非法 objects 不进入正常统计
- 	est_ids_use_same_retry_rules
  - D001、TEST_001、RANDOM_123 使用相同图片和相同响应序列，实际请求次数、错误和重试记录一致

## 5. 自动化测试结果

执行命令：

`powershell
..\project.venv-codex-pytorch\Scripts\python.exe -m unittest discover -s tests -v
`

结果：

- 测试总数：8
- 通过数量：8
- 失败数量：0
- 跳过数量：0
- 错误数量：0

所有新增测试都导入并调用生产代码，没有复制一套独立判断逻辑冒充生产验证。

## 6. 六张真实图片回归情况

本次没有重新调用 Ollama，也没有覆盖已有真实结果目录。当前保存的真实结果保持为：

| 图片 | YOLO | VLM |
|---|---|---|
| D001 | 完成 | verified |
| D002 | 完成 | verified |
| D003 | 完成 | error，MAX_OUTPUT_REACHED |
| D004 | 完成 | verified |
| D005 | 完成 | error，VLM_EMPTY_RESPONSE |
| D006 | 完成 | verified |

这些是真实实验目录中的既有结果。模拟接口只用于 unittest，没有写入 esults/vlm 或 esults/comparison。

## 7. comparison.json 和 CSV 验证

新增测试使用生产 save_comparison，写入临时目录并确认 comparison.json 与 comparison.csv 都包含 verified 状态。

生产 compare_row 现在只把通过 alidate_result_record 的结果写入 lm_counts。非法结果会保留运行时间和错误信息，但 lm_counts 为空，状态为 error。

## 8. Git 修改情况

开始前状态中已有未跟踪的交付包目录和审计报告。本次未删除或修改它们。

本次修改尚未提交，也未推送远程仓库。Git 历史没有被重写。

## 9. 尚未解决的问题

- 本次未重新运行真实 Qwen3-VL，因此真实模型的最新可用性仍以既有结果为准。
- 真实结果中的 D003 和 D005 仍保持原始 error 状态，没有用模拟结果替代。
- done_reason 在兼容部分 Ollama 响应时允许缺失，但 done 必须为 true。存在 done_reason=length 时仍会拒绝。
