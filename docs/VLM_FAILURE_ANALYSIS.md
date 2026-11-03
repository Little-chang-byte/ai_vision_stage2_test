# VLM 失败分析

历史原始响应显示：D002、D003、D005 的 `content` 为空，`thinking` 非空，且 `done_reason` 为 `length`、`eval_count` 达到 300。失败原因是输出被长度上限截断，随后程序没有最终 JSON 可解析。D001、D004、D006 的 `done_reason` 为 `stop` 且 content 含 JSON。

D002 的遮挡、D003 的倾斜、D005 的倒置和多支笔增加了模型描述长度，但不能单独证明它们是根因。证据支持的直接根因是 `done_reason=length` 和 `max_tokens=300`。

图片检查：六张均可解码，RGB，EXIF Orientation 未设置；分辨率在 1280x1707 至 1864x1280。没有覆盖原图，也没有发现传输字段丢失。
