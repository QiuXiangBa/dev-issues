---
title: "Figma 云端 MCP 未授权时改走桌面端 Dev Mode 本地 MCP 读设计稿"
stack: "ai-tools"
platform: [ios, web]
versions: [claude-code 2.1.252, figma-plugin 2.2.111, figma-dev-mode-mcp 1.0.0]
tags: [figma, mcp, oauth, design-to-code, claude-code, json-rpc, svg-rasterize]
project: "tutuai"
status: solved
date: "2026-09-16"
---

## 现象

在 Claude Code 里用 Figma 官方插件（`plugin:figma:figma`，云端 `https://mcp.figma.com/mcp`）做 design-to-code，会话启动时提示：

```
The following MCP servers require authentication before their tools can be used:
plugin:figma:figma
This session is non-interactive, so Claude cannot run the OAuth flow here.
```

`claude mcp list` 显示 `Needs authentication`；`ToolSearch` 找不到任何 figma 工具；直接 WebFetch 设计稿链接返回 403。云端授权过期后会反复出现，非交互会话（Agent SDK / 自动化）没法走 OAuth。

## 原因

云端 Figma MCP 走 OAuth，token 会过期且只能在交互式会话里通过 `/mcp` 重新授权。Figma 桌面端另有一套 Dev Mode MCP Server（设置里 Desktop MCP server settings → Enabled），监听本机 `http://127.0.0.1:3845/mcp`，不需要 OAuth，只要桌面端打开并登录着对应文件即可。它提供 `get_design_context` / `get_metadata` / `get_screenshot` / `get_variable_defs` / `get_motion_context` / `get_figjam`，没有 `use_figma` 等写能力。

## 解决方案

1. 在 Figma 桌面端开启 Desktop MCP server（Image source 选 Local server），确认可达：

```bash
curl -s -X POST http://127.0.0.1:3845/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'
# 返回 serverInfo.name = "Figma Dev Mode MCP Server" 即可用
```

2. 登记到项目，供后续会话直接用：

```bash
claude mcp add --transport http figma-desktop http://127.0.0.1:3845/mcp
```

3. 当前会话已经启动、工具未加载时，可以用 Python 直接发 JSON-RPC（streamable HTTP，响应是 SSE 的 `data:` 行）：initialize → `notifications/initialized` → `tools/call`。把 `Mcp-Session-Id` 响应头带回后续请求。`get_screenshot` 返回 `type: image` 的 base64 PNG，落盘后用 Read 看图。

4. 素材：`get_design_context` 返回的资源是 `http://localhost:3845/assets/<hash>.svg`，`curl` 可直接下载。需要 3x 位图时用 WKWebView 光栅化（`swiftc` 编一个几十行的命令行工具即可，只需 Command Line Tools）；注意 `loadFileURL(_:allowingReadAccessTo:)` 的目录要覆盖 SVG 所在目录，否则图片静默不加载、输出几乎全透明。

5. 已知坑：
   - `get_screenshot` 的 `contentsOnly` 不生效，节点截图会烘焙进 bbox 内的兄弟节点，不能直接当透明素材用；素材从 SVG 自己渲染，方向用「几个候选旋转 / 镜像 → 与节点截图逐像素比对」确定。
   - 整板 `get_design_context` 超出上下文时只返回 metadata，要按子节点分次调用。
   - 画板内容若被旋转 90° 存储，`get_metadata` 里普通节点（instance / text / frame）的换算是 横屏 x = 稿 y、横屏 y = 画板宽 − 稿 x − 稿高；导入的插画组（`_图层_1` / `_隔离模式` / `Group`）的 x,y 不可靠，改用节点截图对整板截图做模板匹配定位。

## 相关链接

- Figma Dev Mode MCP Server 文档：https://help.figma.com/hc/en-us/articles/32132100833559
- 项目内落地记录：QiuXiangBa/tutuai-app#29 的 HANDOFF 评论
