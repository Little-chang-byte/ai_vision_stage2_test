# 三项核心问题修复报告

## 数量累加

原问题位于 VLM 结果生成处，`counts[name] = count` 会覆盖同名记录。`src/vlm_pipeline.py` 现在通过 `aggregate_objects` 标准化名称并累加每条记录，`objects` 和 `counts` 使用同一份累加结果。中文“鼠标”和英文 “computer mouse” 会归并为 `mouse`。

## 返回值校验

新增统一校验入口，拒绝空响应、空对象、错误的 `objects` 类型、缺少 `name/count`、非正整数、浮点数、字符串数量和布尔数量。合法的 `{"objects":[]}` 会通过。Ollama 响应必须包含 `message.content`、`done=true`，并且 `done_reason` 不能是 `length`。失败结果保存 `error`、运行时间、原始响应和每次尝试记录，因此 comparison 中不会把失败标记为 verified。

## 重试策略

已删除按 D001、D004、D005 添加提示词的判断。所有图片统一使用首次提示词，失败后最多重试两次，重试依据错误类型执行，间隔由 `VLM_RETRY_BACKOFF_SECONDS` 配置。图片路径不存在时直接返回 `VLM_IMAGE_NOT_FOUND`，不会进行无意义重试。每次尝试记录 attempt、status、error_type 和响应元数据。

## 自动化测试

`tests/test_vlm_pipeline.py` 使用 Python unittest，覆盖重复类别、多条累加、混合类别、中文英文归并、空数组、空响应、空 JSON、非法数量、截断 JSON，以及 D001 和 TEST_001 的统一重试策略。当前测试结果为 5 passed。

## 真实运行

使用 Ollama `qwen3-vl:4b` 和六张 manifest 图片重新执行。YOLO 六张均完成。VLM 的合法 JSON 状态由新校验逻辑生成。D003 因输出长度达到上限记录为 `MAX_OUTPUT_REACHED`，D005 记录为 `VLM_EMPTY_RESPONSE`，均保留真实失败状态。
