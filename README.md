# dev-issues

AI 开发项目中遇到的问题与解决方案知识库。所有项目共享，通过 Claude Code 全局 Skill `/issues` 访问。

## 接入

新电脑或新成员，一条命令：

```bash
git clone https://github.com/QiuXiangBa/dev-issues.git ~/dev-issues && ~/dev-issues/install.sh
```

脚本做三件事：仓库放到 `~/dev-issues`，把 `claude/skills/issues` 软链到 `~/.claude/skills/issues`，把 `claude/CLAUDE.snippet.md` 追加到 `~/.claude/CLAUDE.md`。重复执行安全，已完成的步骤会跳过。

接入后在任意项目打开 Claude Code，输入 `/issues` 即可。Skill 是软链，`git pull` 后自动生效，不用重新安装。

要求：已安装 git 和 Claude Code，有本仓库的读权限；要写入还需要 push 权限。

## 结构

```
issues/<技术栈>/   每条问题一个 Markdown 文件，文件名 YYYY-MM-DD-slug.md
templates/         新建问题的模板
scripts/           命令行工具：新建、搜索、同步
claude/            Claude Code 接入：/issues Skill 和全局规则片段
install.sh         一键接入
```

### 目录按技术栈分，不按端分

决定解决方案能不能复用的是技术栈，不是端。Flutter 的坑在 iOS 和 Android 上往往是同一个，而 Flutter 和 Swift 在 iOS 上的坑几乎没有交集。目录名用「你会在报错里 grep 的那个框架或语言」：

```
issues/
  swift/        原生 iOS
  kotlin/       原生 Android
  flutter/
  uniapp/
  wechat-mp/    原生小程序
  web/          React、Vue 等前端
  java/
  go/
  ai-tools/     Claude Code、MCP、模型 API
  common/       跨栈通用：网络、鉴权、时区、Git、CI
```

- **目录按需创建**，写第一条时脚本自动建，不预建空目录。名字只允许小写字母、数字、连字符。
- **放不进任何栈的放 `common/`**。判断标准：换个语言这问题还在不在。在，就是 common。
- **不做二级目录**。单个目录超过一百条再考虑。
- **端信息进 `platform` 字段**，允许多值，例如 `platform: [ios, android]`。按端筛用 `search.sh --platform ios`。
- **边界案例**：uniapp 项目里遇到微信平台特有限制，放 `uniapp/`，platform 写 `[wechat]`。原则是放在你改代码的那个框架下。

## 使用

```bash
scripts/search.sh <关键词...>                      # 全文搜索，多个关键词是 AND
scripts/search.sh --in flutter <关键词>            # 限定技术栈
scripts/search.sh --platform ios <关键词>          # 按端过滤
scripts/new-issue.sh <技术栈> "<标题>" [项目名]    # 从模板创建
scripts/sync.sh [提交信息]                         # commit + pull + push
```

在任意项目的 Claude Code 里：

```
/issues search 流式 超时
/issues search --in flutter 热重载
/issues add
/issues list
```

## 记录规范

- `status`: `solved` 已解决 / `open` 未解决 / `workaround` 有临时方案
- `tags`: 小写，用技术名或错误类型，例如 `langchain`, `claude-api`, `timeout`, `json-parse`
- `stack`: 技术栈，与所在目录名相同
- `platform`: 端，多值，可选值 ios / android / wechat / h5 / web / backend
- `project`: 遇到问题的项目名，方便回溯
- 「现象」里尽量粘贴原始报错，检索靠它命中

## 记什么，不记什么

判断标准只有一条：**换一个项目、换一个业务，同样的问题还会再遇到，而且解决方案可以直接复用。**

### 记

- **环境和工具**：Xcode 升级后编译失败、微信开发者工具真机调试连不上、Claude Code 的 MCP 配置不生效、Node 版本冲突。
- **框架和库的行为陷阱**：SDK 在特定版本下的 bug、系统版本导致的 API 行为变化、小程序组件的已知限制和绕法。
- **AI 开发特有问题**：模型返回 JSON 不稳定的兜底、tool_use 参数被截断、上下文超限处理、流式输出中断、提示词在某个模型上失效的原因。
- **通用技术模式**：token 刷新的竞态、跨端时区不一致、大文件分片上传。

### 不记

- **业务逻辑问题**：例如「订单状态机少了退款中状态」。这是项目自己的需求和设计，记在项目文档或 issue 里。
- **一次性配置**：项目的 API 地址、账号、密钥。
- **文档里写清楚的用法**：直接看文档就够的内容。

### 灰色地带

业务问题背后暴露的技术模式值得记。「退款状态机」本身不记，但「状态机在并发回调下重复流转」可以记到 `backend/`，写的时候去掉业务细节，只留模式和解法。

### 快速自测

写完「解决方案」后问自己：明年做一个完全不同的项目遇到同样报错，这段话能不能直接照着做。能就记，不能就是业务问题。
