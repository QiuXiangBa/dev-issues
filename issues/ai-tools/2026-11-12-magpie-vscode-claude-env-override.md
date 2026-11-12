---
title: "Magpie 接入 Claude Code 扩展时旧模型环境变量覆盖配置"
stack: "ai-tools"
platform: []
versions: ["magpie 0.1.3882", "claude-code 2.1.322"]
tags: ["magpie", "vscode", "claude-code", "environment-variables", "model-routing", "streaming"]
project: "https-github-com-yetone-magpie-https"
status: solved
date: "2026-11-12"
---

## 现象

macOS 上安装 Magpie 后，VS Code 官方 Claude Code 扩展仍无法对话，连续出现：

```text
API returned an empty or malformed response (HTTP 200)
content-type none, empty body, 0 bytes, request-id absent
no_events, StreamNoEventsError; 0 stream events received
```

Magpie 中「VS Code」已接入并选择了模型，但「Claude Code」仍为未接入、使用自己的设置；扩展模型栏还显示旧的 Claude 模型。

进一步检查发现，shell 配置仍导出了旧的 `ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_MODEL` 和三档默认模型变量；用户级 Claude Code 配置没有指向 Magpie 的网关地址。项目配置没有覆盖这些接口或模型字段。

## 原因

1. **接入对象不同。** Magpie 的「VS Code」配置的是 VS Code 内建 Chat；官方 Claude Code 扩展通过「Claude Code」接入，使用与 Claude Code CLI 共享的 `~/.claude/settings.json`。前者开启不代表后者已接入。
2. **旧环境变量可以覆盖模型选择。** Claude Code 的模型选择优先级为命令行 `--model`、`ANTHROPIC_MODEL`、settings 顶层 `model`。Magpie 接入后会在 settings 的 `env` 中覆盖接口地址、认证及默认模型映射，但继承的旧 `ANTHROPIC_MODEL` 仍可能盖过顶层模型设置。
3. **不能依赖用户 settings 中的空值长期修复。** 在本次 Magpie 版本中，写入模型档位和同步配置的逻辑会删除 `settings.env.ANTHROPIC_MODEL`，即使值为空。因此只在该位置写空字符串可能在下一次同步或切换模型时失效。

本次没有捕获失败请求实际访问的上游地址，不能把 HTTP 200 空响应直接认定为某个服务端故障或 Magpie 协议转换缺陷。能确认的是接入对象错误和旧模型覆盖同时存在，修正配置后扩展恢复响应。

## 解决方案

1. 先用 Magpie 的只读命令确认网关运行、Claude Code 接入状态以及真实模型 ID：

   ```bash
   magpie status --json
   magpie claude
   magpie models claude
   ```

   检查用户、工作区及本地 settings 中的 `env`、`model`，以及 VS Code 的 `claudeCode.environmentVariables`。检查 shell 配置是否导出旧模型变量；不要直接打印整份环境或凭证文件。

2. 备份 `~/.claude/settings.json` 和 VS Code 用户 settings，然后给 **Claude Code** 选择模型。本次实际使用：

   ```bash
   magpie claude codex/gpt-6.1-sol
   ```

   模型 ID 必须以当前 `magpie models claude` 的结果为准。

3. 在 VS Code 用户设置中，将扩展继承的旧 `ANTHROPIC_MODEL` 清空，让新会话采用 Magpie 管理的模型配置：

   ```json
   {
     "claudeCode.environmentVariables": [
       { "name": "ANTHROPIC_MODEL", "value": "" }
     ]
   }
   ```

   合并到已有的 `claudeCode.environmentVariables` 数组，保留其他条目；同名条目存在时只改它的值。这个设置作用于 VS Code 扩展，避免为了修复扩展而改变其他终端工具的配置。不要把同一修复仅放进 Magpie 会重写的 `settings.env.ANTHROPIC_MODEL`。

4. 运行 VS Code 的 **Developer: Reload Window**，新建 Claude Code 会话。确认模型栏已变为选择的模型；已有会话或显式选择的旧模型可能继续覆盖默认值。

5. 发送最小验证消息：`Reply exactly OK. Do not use tools or read or modify files.` 本次完成了两层验证：Magpie 的 Anthropic Messages 接口返回 HTTP 200、`text/event-stream`、有效事件及 `OK`；VS Code 官方 Claude Code 扩展也实际回复 `OK`。这证明对话链路恢复，不代表已验证所有工具或所有第三方模型能力。

使用期间保持 Magpie 网关运行。若重新选择了旧模型，或项目 settings 有其他覆盖，需要按实际优先级继续检查，不能仅靠扩展模型栏的旧显示判断请求目标。

## 相关链接

- [Magpie 入门：Agent 配置及编辑器前端共享配置](https://usemagpie.ai/docs/start)
- [Magpie 完整参考：Agents 与 Claude Code 配置写入](https://github.com/yetone/magpie/blob/main/docs/reference.md)
- [Magpie Claude Code 适配源码](https://github.com/yetone/magpie/blob/main/internal/agent/claude.go)
- [Claude Code VS Code 扩展配置](https://code.claude.com/docs/en/vs-code#configure-settings)
- [Claude Code 环境变量覆盖规则](https://code.claude.com/docs/en/settings-reference#env)
