---
title: 流式调用下 tool_use 的 input 解析失败
stack: ai-tools
platform: [backend]
versions: [anthropic-python 0.40+, claude-sonnet-4]
tags: [claude-api, tool-use, streaming, json-parse, max-tokens]
project: demo-project
status: solved
date: 2026-09-08
---

## 现象

用 Anthropic Python SDK 流式调用，模型触发 tool_use 时，在 `input_json_delta` 事件里直接 `json.loads` 报错：

```
json.decoder.JSONDecodeError: Unterminated string starting at: line 1 column 27 (char 26)
```

偶发另一种情况：整段流结束后拼出来的 JSON 仍然不完整，`stop_reason` 是 `max_tokens`。

## 原因

两个独立的问题叠在一起：

1. `input_json_delta` 里的 `partial_json` 是分片，单片不是合法 JSON，必须累积到 `content_block_stop` 之后再解析。
2. `max_tokens` 设得太小，模型生成工具参数到一半被截断，此时 `stop_reason == "max_tokens"`，拼出来的 JSON 天然不完整，和分片无关。

## 解决方案

按 content block 累积，结束时再解析；同时检查 `stop_reason`：

```python
buf = {}
with client.messages.stream(model=..., max_tokens=4096, tools=tools, messages=msgs) as stream:
    for event in stream:
        if event.type == "content_block_start" and event.content_block.type == "tool_use":
            buf[event.index] = ""
        elif event.type == "content_block_delta" and event.delta.type == "input_json_delta":
            buf[event.index] += event.delta.partial_json
        elif event.type == "content_block_stop" and event.index in buf:
            args = json.loads(buf[event.index])   # 这里才解析
    final = stream.get_final_message()
if final.stop_reason == "max_tokens":
    raise RuntimeError("工具参数被截断，提高 max_tokens 或让模型减少输出")
```

更省事的做法是不自己处理事件，直接用 `stream.get_final_message()`，SDK 已经把 `input` 拼好了。

## 相关链接

- https://docs.anthropic.com/en/docs/build-with-claude/streaming
- https://docs.anthropic.com/en/docs/build-with-claude/tool-use

> 这是一条示例记录，用来展示格式和详细程度。可以删除。
