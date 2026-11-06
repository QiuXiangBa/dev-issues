---
title: "飞书多维表格单选筛选未知选项返回 1254018 InvalidFilter"
stack: "common"
platform: ["backend"]
versions: ["Feishu Open API bitable v1", "@larksuiteoapi/node-sdk 1.74.0", "Node.js 24.20.0"]
tags: ["feishu", "bitable", "single-select", "filter", "invalid-filter", "metadata", "mock-testing"]
project: "feishuai"
status: solved
date: "2026-11-06"
---

## 现象

给已有飞书多维表格新增单选字段，选项列表初始为空。随后按一个尚未使用过的选项名称查询记录，接口没有返回空列表，而是报错：

```text
code=1254018: InvalidFilter
```

以下使用通用字段名和选项名表示该复现场景：

```text
Invalid request parameter: ''. Correct format : There is no option '示例负责人' for the field '处理人'. Please check and modify accordingly.
```

请求为 `POST /open-apis/bitable/v1/apps/<app_token>/tables/<table_id>/records/search`，筛选条件为：

```json
{
  "filter": {
    "conjunction": "and",
    "conditions": [
      { "field_name": "处理人", "operator": "is", "value": ["示例负责人"] }
    ]
  }
}
```

2026-11-06 的真实接口联调确认：新建单选字段可以没有选项，但按尚不存在的选项名称执行上述筛选会报错。已有选项列表里只有其他名称时，也需要处理未知名称。本记录的实测筛选形式是 `is` 加名称数组，不推断其他操作符的行为。

## 原因

单选字段的查询值需要对应已存在的选项，服务端会校验选项名称；“选项不存在”会被当作非法筛选条件，而不是“没有记录匹配”。

这与写入记录的行为不同：新增或更新记录时，传入新的单选名称可以创建选项。不能把写入接口接受任意新名称的行为套用到查询接口。

本地 mock 最初只比较记录值，既没有模拟写入自动新增单选选项，也没有模拟查询校验选项，因此单元测试通过，真实联调才暴露问题。

## 解决方案

查询前用列出字段接口读取目标字段元数据，检查 `type === 3`（单选）及 `property.options[].name`：

1. 目标名称已存在：继续按名称提交服务端精确筛选，并保留需要的本地精确复核。
2. 目标名称不存在：如果业务查询要求该条件必须成立（单独条件，或与其他条件以 AND 组合），直接返回空列表，不向服务端提交该非法条件。
3. 字段缺失、类型不符、元数据读取失败等情况继续走原有校验和错误处理；不要统一吞掉 `1254018` 或其他 API 错误。

TypeScript 示例（假设 `api.listFields` 已封装字段列表分页）：

```ts
const field = (await api.listFields(tableId))
  .find((f) => f.field_name === fieldName);

if (field?.type === 3) {
  const options = (
    field.property as { options?: { name: string }[] } | undefined
  )?.options ?? [];
  if (!options.some((option) => option.name === requestedName)) {
    return { items: [], truncated: false };
  }
}

// 名称存在时沿用服务端 is + value:[requestedName] 筛选。
// 字段缺失或类型不符时，交给原有校验 / 查询路径处理。
return searchRecordsWithRequiredOption(fieldName, requestedName);
```

这个提前返回只适用于该单选条件必须成立的查询。若条件放在 OR 中，其他分支仍可能匹配，不能据此把整个查询变成空结果。

读取时不要为了绕过报错而预先创建选项；查询应保持只读。字段列表应完整分页，避免漏读字段后错误判断。

同步修正 mock。回归测试应覆盖：

- 新建单选字段没有任何选项，查询任意名称返回业务空列表，且不提交记录筛选请求。
- 字段已有其他选项，查询未知名称仍返回空列表。
- 新增或更新记录写入新名称后，mock 自动补入选项，该名称随后可以被筛选到。
- mock 对未知单选选项的服务端筛选返回 `1254018`，包括记录表为空的情况。
- 已有选项保持精确匹配，权限、网络等异常不被转换为空结果。

修复后已在真实表验证：查询尚未创建的名称成功返回空列表；查询过程没有创建选项或修改任务记录。

## 相关链接

- [飞书：列出字段](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-field/list)
- [飞书：查询记录](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/search)
- [飞书：新增记录](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/create)

上述链接用于定位 API；未知单选选项的报错与修复验证来自本次真实联调，不能据此声称文档明确承诺了全部边界行为。
