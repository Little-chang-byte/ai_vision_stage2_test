# 三项考核反馈代码审计报告

## 1. 审计概况

- 审计时间：2026-11-04 22:03:34（本机时间）
- 工作目录：D:\后端_test\ai_vision_stage2
- Git 分支：main
- 当前提交：5e55ace fix: validate vlm results and aggregate counts
- 远程跟踪：origin/main 仍指向上一提交 581243b，本次修复提交尚未推送到远程。
- 工作区：没有已跟踪文件修改，没有暂存修改。存在之前生成的未跟踪交付包目录，未纳入本次审计修改。
- 审计范围：src/vlm_pipeline.py、src/comparison.py、src/main.py、src/traditional_pipeline.py、	ests/test_vlm_pipeline.py、data/manifest.csv、esults/vlm/、esults/traditional/、esults/comparison/。
- 审计边界：本次只读检查，新增本报告是唯一文件写入操作。未修改源码、测试、配置、图片、历史结果或 Git 历史。

## 2. 问题一：同类数量累加

结论：**PASS**。

代码证据：

- src/vlm_pipeline.py:20-37 的 ggregate_objects 先调用 
ormalize_name，再使用 	otals[name] = totals.get(name, 0) + count 累加。
- src/vlm_pipeline.py:35-37 同时生成合并后的 objects 和 counts，避免后续再次用直接赋值覆盖。
- src/vlm_pipeline.py:12-18 将“鼠标”“computer mouse”等名称标准化为 mouse，并将“键盘”映射为 keyboard。
- src/traditional_pipeline.py:16 的 YOLO 统计使用独立的 Counter，没有复用 VLM 统计状态。
- src/comparison.py:6 直接读取 YOLO 和 VLM 各自保存的 counts，没有重新覆盖计数。

实际测试证据：

- 	est_duplicate_counts 直接调用生产函数 ggregate_objects，验证两个 mouse 得到 2，三条 mouse 数量 1、2、1 与一个 keyboard 得到 mouse=4、keyboard=1。
- 	est_alias_and_empty 验证“鼠标”与“computer mouse”合并为 mouse=3，并验证合法空数组得到空统计。
- 真实保存结果中 D004 的 VLM 结果为 {"book":2}，说明重复类别会保留累加值。
- comparison.json 中的 lm_counts 与对应 esults/vlm/*.json 的 counts 一致。审计读取到 D001-D006 共 6 条结果。

风险：

- 当前 ggregate_objects 仍允许字符串条目，例如 "mouse"，并将其按 count=1 处理，见 src/vlm_pipeline.py:24-25。这兼容了项目早期的简化提示词，但严格 Schema 若要求每个条目必须包含 
ame 和 count，该兼容行为会放宽校验边界。因此数量累加本身通过，严格 Schema 一致性需标记为审计风险。

## 3. 问题二：返回值校验

结论：**PARTIAL**。

已验证的代码行为：

- src/vlm_pipeline.py:45-52 拒绝 None、空字符串、空白字符串和非法 JSON。
- src/vlm_pipeline.py:39-43 拒绝缺少 objects、objects=null、objects 非数组以及空对象 {}。
- {"objects":[]} 可以通过 alidate_payload，与空响应区分开。
- src/vlm_pipeline.py:27-31 拒绝缺少 name/count、负数、零、浮点数、字符串数量和布尔数量。
- src/vlm_pipeline.py:54-57 使用 Ollama 原生 /api/chat，请求中带有 stream=false。
- src/vlm_pipeline.py:71-80 检查 message、content、done=true、done_reason 和完整 JSON。done_reason=length 会生成 MAX_OUTPUT_REACHED。
- src/comparison.py:6 只有 VLM 结果没有 error 且存在运行时间时才标记 verified。错误结果不会因为 JSON 或运行时间存在而通过。

实际测试证据：

- 	est_invalid_values 使用生产函数，覆盖空响应、空对象、objects=null、objects 为字符串、负数、浮点数、字符串、null、true 和缺少 count。全部通过拒绝断言。
- 	est_truncated_json_rejected 验证未闭合 JSON 被拒绝。
- 完整自动化测试命令为 ..\\project.venv-codex-pytorch\\Scripts\\python.exe -m unittest discover -s tests -v，结果为 Ran 5 tests ... OK。
- 六张真实结果中 D003 为 rror=MAX_OUTPUT_REACHED，D005 为 rror=VLM_EMPTY_RESPONSE。两者均没有进入 verified，证明真实 Ollama 响应的失败状态被保存。

为何不是 PASS：

- src/vlm_pipeline.py:24-25 接受字符串对象并隐式补 count=1，严格审计要求中“缺少 count 必须 error”。现有测试没有覆盖 {"objects":["mouse"]} 这一生产入口的拒绝要求，当前实现会接受它。
- src/vlm_pipeline.py:77 允许缺少 done_reason，前提是 done=true。这符合部分 Ollama 响应兼容性，但无法证明所有服务版本都提供正常结束原因。
- src/comparison.py:6 的 verified 判断依赖上游 payload 的 rror 和 untime_seconds，没有在比较层重新验证 Schema。当前生产入口已经先校验，因此未发现实际错误流入，但比较模块本身不是完全独立的安全边界。

## 4. 问题三：统一重试机制

结论：**PASS**。

代码证据：

- src/vlm_pipeline.py:8-10 统一配置 MAX_RETRIES、退避时间和可重试错误集合。
- src/vlm_pipeline.py:68-91 所有图片都使用相同的循环、相同的首次/重试提示词、相同的最大次数和错误分类。
- 生产源码中没有发现 image_id in {...} 或按 D001-D006 改变提示词、次数或错误处理的逻辑。
- src/vlm_pipeline.py:64-65 图片不存在时直接返回 VLM_IMAGE_NOT_FOUND。
- src/vlm_pipeline.py:81、87、92-95 保存每次尝试、原始响应和最终结构化结果。

实际测试证据：

- 	est_ids_use_same_retry_rules 创建相同内容的临时图片，分别调用 D001 与 TEST_001，使用相同空响应序列，断言两者均经历 attempt 1、2、3 且最终错误相同。
- g 搜索结果只发现测试中的 D001 字符串和 main.py 的通用 image_id 读取，没有生产重试特殊分支。
- 测试结果为 5/5 通过。

风险：

- 本次现有测试只直接比较 D001 与 TEST_001，没有按要求再覆盖 RANDOM_123。生产循环没有 ID 分支，代码证据充分，但三种 ID 的实调用证据不完整。
- 当前 MAX_RETRIES=2 代表最多三次请求，变量命名容易让读者误解为总请求次数。行为本身有限且无无限重试。

## 5. 自动化测试结果

执行命令：

`powershell
..\project.venv-codex-pytorch\Scripts\python.exe -m unittest discover -s tests -v
`

结果：

- 测试总数：5
- 通过：5
- 失败：0
- 跳过：0
- 错误：0

测试文件为 	ests/test_vlm_pipeline.py。测试确实导入并调用 src/vlm_pipeline.py 的生产函数，没有单独复制生产逻辑。

测试覆盖了数量累加、类别归并、合法空数组、非法响应、非法数量、截断 JSON 和两个不同图片 ID 的重试次数。

测试覆盖不足之处是没有验证完整 main.py -> comparison.save_comparison 的模拟响应链路，也没有覆盖 RANDOM_123 的实际调用。

## 6. 六张真实图片回归状态

数据来源为 data/manifest.csv，六张图片均为个人拍摄，YOLO 和 VLM 使用同一 manifest 路径。当前已有结果如下：

| image_id | YOLO | VLM 状态 | VLM 错误 |
|---|---|---|---|
| D001 | 完成 | verified | 无 |
| D002 | 完成 | verified | 无 |
| D003 | 完成 | error | MAX_OUTPUT_REACHED |
| D004 | 完成 | verified | 无 |
| D005 | 完成 | error | VLM_EMPTY_RESPONSE |
| D006 | 完成 | verified | 无 |

审计读取了 esults/comparison/comparison.json。当前结果为 4/6 verified、2/6 error。没有把 D003 或 D005 的失败记录改写为成功。

本次审计没有重新运行真实模型，也没有覆盖已有结果文件，遵守了非破坏性审计边界。因此真实回归结论基于当前保存的真实运行产物和历史执行记录，不能替代本次重新推理。

## 7. 尚存问题

- 问题二存在严格 Schema 边界风险。字符串形式的 object 会被当作 count=1 接受，未完全满足“缺少 count 必须拒绝”的审计要求。
- comparison.py 依赖上游 error 字段和运行时间判断 verified，比较层没有重复执行完整 Schema 校验。
- 测试没有覆盖 RANDOM_123，也没有覆盖完整入口生成 comparison 文件的模拟链路。
- 当前 HEAD 为 5e55ace，远程 origin/main 仍在 581243b。如果考核查看 GitHub，之前的修复提交尚未同步到远程。
- 当前工作区有未跟踪的交付包目录。审计未删除或修改它。
- 本次没有重新调用 Ollama，无法对当前时刻的服务可用性做新的网络结论。

## 8. 最终验收结论

- 同类数量累加：**PASS**。生产聚合函数使用标准化名称和加法，5 个自动化测试中的数量与别名断言通过，D004 真实结果也保留了 book=2。
- 返回值校验：**PARTIAL**。空响应、非法 JSON、非法数量、截断和真实失败状态均被拦截，但字符串对象兼容分支放宽了 count 必需约束，比较层也没有独立 Schema 防线。
- 统一重试机制：**PASS**。生产代码没有图片 ID 特殊分支，统一按错误类型和固定次数重试，D001 与 TEST_001 的相同异常序列测试通过。
