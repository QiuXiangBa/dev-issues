---
name: issues
description: 跨项目共享的 AI 开发问题知识库。搜索、新增、更新、列出已记录的问题与解决方案。用法 /issues search <关键词>、/issues add、/issues update <关键词>、/issues list。遇到报错或调试卡住时先用 search；问题解决后用 add 记录。
---

# 问题知识库

仓库位于 `~/dev-issues`，远端 https://github.com/QiuXiangBa/dev-issues 。每条问题是 `issues/<技术栈>/` 下一个 Markdown 文件，带 frontmatter：title / stack / platform / versions / tags / project / status / date。目录按技术栈分（swift、kotlin、flutter、uniapp、wechat-mp、web、java、go、ai-tools、common），不按端分；端信息在 `platform` 字段里，允许多值。

## 项目侧声明

执行 search、add、update 前，先看当前项目根目录的 `CLAUDE.md` 有没有「## 问题知识库」一节。格式：

```markdown
## 问题知识库
- 技术栈目录：uniapp
- 端：[wechat, h5]
```

有声明就直接用，不要再扫项目文件猜。没有声明才按下面各子命令里的规则推断。

## 子命令

参数 `$ARGUMENTS` 的第一个词是子命令，其余是参数。没有子命令时按 `search` 处理。

### search [--in <技术栈>] [--platform <端>] <关键词...>

1. 先执行 `cd ~/dev-issues && git pull --rebase --autostash --quiet` 拉最新。
2. 准备关键词。取用户给的词，加上从当前报错里提取的 2 到 3 个关键 token（库名、错误类型、函数名）。中文关键词补一版英文，英文补一版中文，例如「超时」和 timeout 都搜。
3. 执行 `~/dev-issues/scripts/search.sh [--in 栈] [--platform 端] <关键词...>`。多个关键词是 AND 关系，先用中文版搜，再用英文版搜，都没结果就减少关键词各重试一次。技术栈优先取项目侧声明，没有声明再从项目文件判断。能判断时先用 `--in` 搜，没结果再去掉 `--in` 全库搜一次。
4. 命中后用 Read 读取最相关的 1 到 3 个文件，向用户总结「原因」和「解决方案」，并给出文件路径。留意 `versions` 字段，如果记录的版本和用户当前版本差得远，提醒解法可能已过时。
5. 没有命中就明确说没有记录，不要编造。

### add

把当前对话里刚解决的问题记录下来。

0. 先按「记录标准」判断这个问题是否属于这个库。不属于就告诉用户原因，建议记到项目自己的文档或 issue，然后停止。灰色地带的问题可以记，但要去掉业务细节，只保留技术模式和解法。
1. 判断技术栈目录。先看项目侧声明，有就用声明的目录和端。没有声明再看当前项目文件：Package.swift 或 .xcodeproj 是 swift，build.gradle 是 kotlin，pubspec.yaml 是 flutter，manifest.json 加 pages.json 是 uniapp，app.json 加 project.config.json 是 wechat-mp，package.json 带 react 或 vue 是 web，pom.xml 或 build.gradle 带 spring 是 java，go.mod 是 go；问题出在 Claude Code、MCP、模型 API 上是 ai-tools；换个语言问题还在的是 common。判断不了就问用户，不要猜。目录名小写，先用 `ls ~/dev-issues/issues` 看已有目录，优先复用。
2. 查重。用标题里的 2 到 3 个关键词（中英文各一版）执行 `search.sh --in <栈>`。命中且确实是同一个问题，就改走 update 流程在原记录上追加，不要新建。
3. 从对话中提炼：一句话标题、英文 slug（3 到 6 个词，小写连字符，例如 `tool-use-json-truncated`）、现象（尽量带原始报错）、原因、解决方案、相关链接、涉及的框架和工具版本。项目名取当前工作目录名。
4. 执行 `~/dev-issues/scripts/new-issue.sh <技术栈> <slug> "<标题>" "<项目名>"` 得到文件路径。
5. 用 Edit 填充 frontmatter 的 platform（多值，可选 ios / android / wechat / h5 / web / backend；项目侧有声明就直接填声明的值）、versions（例如 `[flutter 3.24.0, xcode 16.1]`，不知道就问用户或从 lock 文件读）、tags、status，以及正文各节。tags 小写，用技术名或错误类型。
6. 推送前做脱敏检查。仓库是公开的，逐项检查刚写入的内容：
   - 密钥、token、密码、Authorization 头、cookie
   - 内网 IP、内部域名、服务器主机名
   - 账号、手机号、邮箱、真实用户数据
   - 客户名、未公开的产品名、业务数据
   发现就替换成占位符，例如 `sk-***`、`10.x.x.x`、`user@example.com`、`<客户名>`。替换后把改了哪些项告诉用户，由用户确认再推送。没发现就直接说「未发现敏感信息」。
7. 执行 `~/dev-issues/scripts/sync.sh "add: <标题>"` 推送。索引 INDEX.md 会自动更新。
8. 向用户回报文件路径。如果对话中信息不够，先问用户缺哪一项，不要留空模板。

### update <关键词...>

给已有记录补充信息或改状态。典型场景：之前记为 `open` 或 `workaround` 的问题现在彻底解决了，或者发现新版本里行为变了。

1. 按 search 的方式定位记录。命中多条就列出让用户选，不要猜。
2. 不改动原有正文。在文末追加一节：

   ```markdown
   ## 更新 YYYY-MM-DD

   <补充的内容：新的解法、新版本的变化、原方案失效的原因>
   ```
3. 需要的话改 frontmatter 的 status，并把新版本追加到 versions。
4. 同 add 的脱敏检查。
5. 执行 `~/dev-issues/scripts/sync.sh "update: <标题>"` 推送。

### list [技术栈|status]

直接 Read `~/dev-issues/INDEX.md` 展示给用户。参数是目录名就只展示该节，是 solved / open / workaround 就只列该状态的行。

## 注意

- 写入前必须 pull，写入后必须 push，否则多设备会冲突。sync.sh 遇到冲突会打印处理步骤，原样转告用户。
- 仓库是公开的。任何写入操作，包括 add 和 update，推送前都要做脱敏检查。
- 不要修改已有记录的正文，只能通过 update 追加。
- INDEX.md 由脚本生成，不要手改。

## 记录标准

只记**换一个项目、换一个业务还会再遇到，且解法可直接复用**的技术问题：

- 记：环境和工具问题、框架和库的行为陷阱、AI 开发特有问题（模型输出不稳定、tool_use 截断、上下文超限、流式中断、提示词失效）、通用技术模式（并发竞态、时区、分片上传）。
- 不记：业务逻辑问题（属于项目自己的需求设计）、一次性配置（地址、账号、密钥）、文档里已写清楚的用法。
- 灰色地带：业务问题背后的技术模式可以记，写的时候去掉业务细节。

自测：明年做一个完全不同的项目遇到同样报错，这段「解决方案」能不能直接照着做。能就记。
