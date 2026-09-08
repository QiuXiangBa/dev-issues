---
name: issues
description: 跨项目共享的 AI 开发问题知识库。搜索、新增、列出已记录的问题与解决方案。用法 /issues search <关键词>、/issues add、/issues list。遇到报错或调试卡住时先用 search；问题解决后用 add 记录。
---

# 问题知识库

仓库位于 `~/dev-issues`，远端 https://github.com/QiuXiangBa/dev-issues 。每条问题是 `issues/<技术栈>/` 下一个 Markdown 文件，带 frontmatter：title / stack / platform / tags / project / status / date。目录按技术栈分（swift、kotlin、flutter、uniapp、wechat-mp、web、java、go、ai-tools、common），不按端分；端信息在 `platform` 字段里，允许多值。

## 子命令

参数 `$ARGUMENTS` 的第一个词是子命令，其余是参数。没有子命令时按 `search` 处理。

### search [--in <技术栈>] [--platform <端>] <关键词...>

1. 先执行 `cd ~/dev-issues && git pull --rebase --quiet` 拉最新。
2. 执行 `~/dev-issues/scripts/search.sh [--in 栈] [--platform 端] <关键词...>`。关键词取用户给的词，加上从当前报错里提取的 2 到 3 个关键 token（库名、错误类型、函数名）。多个关键词是 AND 关系，没结果时减少关键词重试一次。能从当前项目判断技术栈时先用 `--in` 搜，没结果再去掉 `--in` 全库搜一次。
3. 命中后用 Read 读取最相关的 1 到 3 个文件，向用户总结「原因」和「解决方案」，并给出文件路径。
4. 没有命中就明确说没有记录，不要编造。

### add

把当前对话里刚解决的问题记录下来。

0. 先按「记录标准」判断这个问题是否属于这个库。不属于就告诉用户原因，建议记到项目自己的文档或 issue，然后停止。灰色地带的问题可以记，但要去掉业务细节，只保留技术模式和解法。
1. 判断技术栈目录。看当前项目：Package.swift 或 .xcodeproj 是 swift，build.gradle 是 kotlin，pubspec.yaml 是 flutter，manifest.json 加 pages.json 是 uniapp，app.json 加 project.config.json 是 wechat-mp，package.json 带 react 或 vue 是 web，pom.xml 或 build.gradle 带 spring 是 java，go.mod 是 go；问题出在 Claude Code、MCP、模型 API 上是 ai-tools；换个语言问题还在的是 common。判断不了就问用户，不要猜。目录名小写，先用 `ls ~/dev-issues/issues` 看已有目录，优先复用。
2. 从对话中提炼：一句话标题、现象（尽量带原始报错）、原因、解决方案、相关链接。项目名取当前工作目录名。
3. 执行 `~/dev-issues/scripts/new-issue.sh <技术栈> "<标题>" "<项目名>"` 得到文件路径。
4. 用 Edit 填充 frontmatter 的 platform（多值，可选 ios / android / wechat / h5 / web / backend）、tags、status，以及正文各节。tags 小写，用技术名或错误类型。
5. 执行 `~/dev-issues/scripts/sync.sh "add: <标题>"` 推送。
6. 向用户回报文件路径。如果对话中信息不够，先问用户缺哪一项，不要留空模板。

### list [技术栈|status]

执行 `grep -rH '^title:\|^status:' ~/dev-issues/issues`，按技术栈目录分组列出标题和文件名。参数是目录名就只列该目录，是 solved / open / workaround 就只列该状态。

## 注意

- 写入前必须 pull，写入后必须 push，否则多设备会冲突。
- 不要修改已有记录的正文，除非用户明确要求。补充信息时在文末追加「更新 YYYY-MM-DD」段落。

## 记录标准

只记**换一个项目、换一个业务还会再遇到，且解法可直接复用**的技术问题：

- 记：环境和工具问题、框架和库的行为陷阱、AI 开发特有问题（模型输出不稳定、tool_use 截断、上下文超限、流式中断、提示词失效）、通用技术模式（并发竞态、时区、分片上传）。
- 不记：业务逻辑问题（属于项目自己的需求设计）、一次性配置（地址、账号、密钥）、文档里已写清楚的用法。
- 灰色地带：业务问题背后的技术模式可以记，写的时候去掉业务细节。

自测：明年做一个完全不同的项目遇到同样报错，这段「解决方案」能不能直接照着做。能就记。
