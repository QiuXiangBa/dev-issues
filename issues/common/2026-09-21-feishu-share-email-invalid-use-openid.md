---
title: "飞书开放平台按邮箱给个人账号授权文档返回 1063001，需按手机号换 open_id"
stack: "common"
platform: [backend]
versions: ["@larksuiteoapi/node-sdk 1.74.0", "feishu open-apis drive v1 / contact v3"]
tags: [feishu, lark, permission, open-id, tenant-access-token, bitable, docx]
project: "feishuai"
status: solved
date: "2026-09-21"
---

## 现象

用应用身份（`tenant_access_token`）调用「增加协作者」接口，把应用自己创建的多维表格 / 新版文档授权给用户：

```
POST /open-apis/drive/v1/permissions/<token>/members?type=bitable
{"member_type": "email", "member_id": "user@example.com", "perm": "full_access"}
```

返回：

```json
{"code": 1063001, "msg": "Invalid parameter"}
```

换 `perm: edit`、换 `type: docx` 结果一样。排查页只显示"参数错误"，看不出是哪个参数。

背景：应用以租户身份 `POST /open-apis/bitable/v1/apps` 或 `POST /open-apis/docx/v1/documents` 创建的资源位于**应用自己的云空间根目录**，用户在飞书里看不到，必须授权后才可见；而且用 `tenant_access_token` 创建时 `folder_token` 只能指定应用自己创建的文件夹，无法直接放进用户的文件夹。

## 原因

`member_type: email` 只能匹配租户通讯录里绑定了该邮箱的账号。个人版 / 小团队的飞书账号通常只用手机号注册，通讯录里邮箱字段为空，用户自认为的邮箱（如 QQ 邮箱）并没有绑定，接口按"找不到成员"处理并返回 1063001 而不是更明确的错误。

验证方法：`POST /open-apis/contact/v3/users/batch_get_id`（`user_id_type=open_id`）传 `emails` 时返回的条目只有 `email` 没有 `user_id`，说明邮箱未绑定；传 `mobiles` 则返回 `user_id`（即 open_id）。

## 解决方案

1. 给应用开通权限 `contact:user.id:readonly`（通过手机号或邮箱获取用户 ID），重新发布版本。
2. 按手机号换 open_id：

```bash
curl -X POST 'https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id?user_id_type=open_id' \
  -H 'Authorization: Bearer t-***' -H 'Content-Type: application/json' \
  -d '{"mobiles": ["<手机号>"]}'
# → {"user_list":[{"mobile":"<手机号>","user_id":"ou_xxxxxxxx"}]}
```

3. 用 `openid` 类型授权：

```bash
curl -X POST 'https://open.feishu.cn/open-apis/drive/v1/permissions/<token>/members?type=bitable&need_notification=false' \
  -H 'Authorization: Bearer t-***' -H 'Content-Type: application/json' \
  -d '{"member_type": "openid", "member_id": "ou_xxxxxxxx", "perm": "full_access"}'
```

`type` 按资源填 `bitable` / `docx` / `folder`；所需 scope 任一：`docs:permission.member:create`、`drive:drive`、`bitable:app`（多维表格）。

通用建议：代码里根据标识自动选 `member_type`（`ou_` 开头 → `openid`，含 `@` → `email`，否则 `userid`），并把授权目标配置成 open_id 而不是邮箱；应用创建资源后立即授权，否则用户根本看不到。

## 相关链接

- 增加协作者：https://open.feishu.cn/document/server-docs/docs/permission/permission-member/create
- 通过手机号或邮箱获取用户 ID：https://open.feishu.cn/document/server-docs/contact-v3/user/batch_get_id
- 创建多维表格（tenant_access_token 对 folder_token 的限制）：https://open.feishu.cn/document/server-docs/docs/bitable-v1/app/create
