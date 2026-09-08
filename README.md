# dev-issues

AI 开发项目中遇到的问题与解决方案知识库。所有项目共享，通过 Claude Code 全局 Skill `/issues` 访问。

## 接入

新电脑或新成员，一条命令：

```bash
git clone https://github.com/QiuXiangBa/dev-issues.git ~/dev-issues && ~/dev-issues/install.sh
```

脚本做三件事：仓库放到 `~/dev-issues`，把 `claude/skills/issues` 软链到 `~/.claude/skills/issues`，把 `claude/CLAUDE.snippet.md` 写入 `~/.claude/CLAUDE.md` 的受管区块。重复执行会更新区块内规则，保留区块外的个人配置；已有仓库会先核对 origin，避免接入错误仓库。

接入后在任意项目打开 Claude Code，输入 `/issues` 即可。Skill 是软链，`git pull` 后自动生效；全局规则片段有更新时，重新执行 `~/dev-issues/install.sh`。

规则区块使用 `<!-- dev-issues:begin -->` 和 `<!-- dev-issues:end -->` 标记。与当前片段完全一致的旧版规则会自动迁移；自定义的同名规则不会被覆盖，脚本会提示如何标记需要更新的区块。已有的其他 Skill 目录或失效软链也不会被覆盖。

前置条件：已安装 Git、Python 3.9+ 和 Claude Code。脚本只依赖 Python 标准库，不需要 pip 安装。自动检查覆盖 macOS 和 Linux；Windows 请使用 WSL。仓库是公开的，clone 不需要登录。要用 `/issues add` 写入记录则需要 push 权限，先登录 GitHub 并被加为协作者：

```bash
brew install gh && gh auth login    # 或者配好 SSH key 后把 remote 换成 git@github.com:QiuXiangBa/dev-issues.git
```

只读使用的话，跳过这一步即可。

## 项目侧配置（可选）

接入后所有项目自动生效，项目自己的 CLAUDE.md 不需要改任何东西。

只有一种情况值得加：`/issues add` 默认靠扫项目文件推断技术栈，混合项目或 monorepo 可能猜错或停下来问。在项目的 `CLAUDE.md` 里加两行就不用猜了：

```markdown
## 问题知识库
- 技术栈目录：uniapp
- 端：[wechat, h5]
```

技术栈目录写 `issues/` 下的目录名，端写 platform 字段的值。加了以后 `/issues search` 先在该目录下搜，`/issues add` 直接写进该目录并自动填 platform。

## 结构

```
issues/<技术栈>/   每条问题一个 Markdown 文件，文件名 YYYY-MM-DD-<slug>.md，slug 为英文
INDEX.md           自动生成的索引，按技术栈分组，不要手改
templates/         新建问题的模板
scripts/           Shell 命令入口、共享 Python 解析与校验、同步和安装配置
tests/             隔离的命令行和本地 Git 回归测试
claude/            Claude Code 接入：/issues Skill 和全局规则片段
install.sh         一键接入
```

看全部记录：[INDEX.md](INDEX.md)。示例记录：[issues/ai-tools/2026-09-08-tool-use-json-truncated.md](issues/ai-tools/2026-09-08-tool-use-json-truncated.md)，照这个详细程度写。

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
scripts/search.sh <关键词...>                              # 全文搜索，多个关键词是 AND
scripts/search.sh --in flutter <关键词>                    # 限定技术栈
scripts/search.sh --platform ios <关键词>                  # 按端过滤
scripts/new-issue.sh <技术栈> <slug> "<标题>" [项目名]     # 从模板创建，slug 为英文小写连字符
scripts/index.sh                                           # 重新生成 INDEX.md
scripts/index.sh --check                                   # 检查索引是否与记录一致
scripts/validate.sh [记录路径...]                          # 校验指定记录，不传路径则校验全库
scripts/sync.sh [-m "提交信息"] <记录路径...>              # 只同步指定记录及生成的索引
scripts/sync.sh --check <记录路径...>                      # 校验并 fetch，不提交、不推送
```

路径参数支持仓库相对路径（`issues/common/2026-09-08-example.md`）或仓库内的绝对路径。搜索不区分大小写，默认按字面量匹配，多个关键词为 AND；可以单独使用 `--in` 或 `--platform` 列出记录。搜索以 `-` 开头的关键词时使用 `scripts/search.sh -- --keyword`。无匹配返回 0；参数、读取或格式错误返回非 0，不会被伪装成无结果。

同步命令不再接受旧版的单个提交信息参数，改用 `-m`，并明确列出本次文件。它会先检查记录格式、正文完整性及常见敏感信息，再 fetch、提交记录、rebase、重新生成索引并推送到当前分支的 upstream。索引只收录 Git 已跟踪的记录，不会把其他未跟踪记录带入提交。同步会重建本地 `INDEX.md`，请勿手工编辑它。

有其他已跟踪修改或暂存文件时，同步会停止并保留现场；请先单独提交或 stash。其他未跟踪文件保留原样。待推送的每个本地提交也会检查文件范围和敏感信息，避免把之前的无关提交或已从最终版本移除的密钥一起推送。

多人新增不同记录时，索引在 rebase 后生成；若重试时仅索引冲突，会自动重建。记录正文冲突则保留 rebase 状态并提供处理步骤。网络、鉴权、upstream 配置和推送失败分别保留 Git 错误；推送失败后本地提交仍在，处理原因后使用原命令重试。`git rebase --abort` 只取消 rebase，不删除此前的本地提交。

在任意项目的 Claude Code 里：

```
/issues search 流式 超时          # 中英文关键词都会搜，先搜当前项目的技术栈再搜全库
/issues add                       # 先查重再新建，推送前脱敏检查
/issues update 热重载             # 给已有记录追加「更新」段落、改状态
/issues list [技术栈|status]      # 展示索引
```

## 记录规范

- `status`: `solved` 已解决 / `open` 未解决 / `workaround` 有临时方案
- `tags`: 小写，用技术名或错误类型，例如 `langchain`, `claude-api`, `timeout`, `json-parse`
- `stack`: 技术栈，与所在目录名相同
- `platform`: 端，多值，可选值 ios / android / wechat / h5 / web / backend
- `versions`: 涉及的框架和工具版本，例如 `[flutter 3.24.0, xcode 16.1]`。框架的坑大多和版本相关，不记一年后就没法判断还适不适用
- `project`: 遇到问题的项目名，方便回溯
- 「现象」里尽量粘贴原始报错，检索靠它命中
- 文件名的 slug 用英文，标题用中文放 frontmatter。中文文件名在 GitHub 链接里会变成一长串编码，Windows 上还可能乱码
- **已有记录不改正文**。补充信息用 `/issues update`，在文末追加「## 更新 YYYY-MM-DD」段落，保留演变过程
- **仓库是公开的，写入前脱敏**：密钥、内网地址、账号、手机号、邮箱、客户名、业务数据一律替换成占位符，例如 `sk-***`、`10.x.x.x`、`user@example.com`、`<客户名>`。`/issues add` 推送前会自动检查一遍，但最终责任在提交的人

Frontmatter 使用受限的 YAML 格式：字段为单行字符串或单行字符串数组，例如 `platform: [ios, android]`、`versions: ["tool 1, build 2"]`。标题、项目名包含 `: `、` #`、引号或其他特殊字符时，使用 JSON 双引号字符串（双引号写成 `\"`，反斜杠写成 `\\`）；新建脚本自动处理。支持 YAML 单引号字符串，不支持多行值、嵌套对象、锚点和别名。未知或重复字段、非法状态/端/标签、日期与文件名不一致、stack 与目录不一致均会报错。新建时允许空正文用于编辑，同步前「现象」「原因」「解决方案」必须填写。

同步的敏感信息检查覆盖常见密钥、认证头、凭据赋值、私网 IPv4、内部域名后缀、手机号和非示例邮箱；报错仅显示路径、行号和类别。它不能判断客户名、业务数据或任意格式的凭据，仍需人工或 Skill 审阅全部本次内容。命中后使用占位符脱敏；历史提交中命中时，需要先清理尚未推送的本地历史。

## 开发检查

```bash
python3 -m unittest discover -s tests -v
scripts/validate.sh
scripts/index.sh --check
```

测试使用临时目录和本地 bare Git 仓库，覆盖特殊字符、带空格路径、格式错误、同步范围、敏感信息、并发新增、推送失败重试、正文冲突和安装规则升级。GitHub Actions 在 macOS、Linux 上执行测试、Shell 语法及索引一致性检查。

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

业务问题背后暴露的技术模式值得记。「退款状态机」本身不记，但「状态机在并发回调下重复流转」可以记下来，放在改代码的那个栈下（`java/`、`go/`），换个语言问题还在的放 `common/`。写的时候去掉业务细节，只留模式和解法。

### 快速自测

写完「解决方案」后问自己：明年做一个完全不同的项目遇到同样报错，这段话能不能直接照着做。能就记，不能就是业务问题。
