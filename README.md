# dev-issues

AI 开发项目中遇到的问题与解决方案知识库。所有项目共享，通过 Claude Code 全局 Skill `/issues` 访问。

## 结构

```
issues/       每条问题一个 Markdown 文件，文件名 YYYY-MM-DD-slug.md
templates/    新建问题的模板
scripts/      命令行工具：新建、搜索、同步
```

## 使用

```bash
scripts/search.sh <关键词>            # 全文搜索，支持多个关键词
scripts/new-issue.sh "<标题>"          # 从模板创建一条记录并打开
scripts/sync.sh                        # pull + commit + push
```

在任意项目的 Claude Code 里：

```
/issues search 流式 超时
/issues add
/issues list
```

## 记录规范

- `status`: `solved` 已解决 / `open` 未解决 / `workaround` 有临时方案
- `tags`: 小写，用技术名或错误类型，例如 `langchain`, `claude-api`, `timeout`, `json-parse`
- `project`: 遇到问题的项目名，方便回溯
- 「现象」里尽量粘贴原始报错，检索靠它命中
