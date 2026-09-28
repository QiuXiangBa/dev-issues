---
title: "飞书自建应用换 App ID 后 CLI 全线 99991672 / 91403 / open_id cross app：scope、open_id、资源授权都按应用隔离"
stack: "common"
platform: [backend]
versions: ["@larksuiteoapi/node-sdk 1.74.0", "@larksuite/cli 1.0.96", "feishu open-apis bitable v1 / drive v1 / calendar v4 / contact v3"]
tags: [feishu, lark, permission, scope, open-id, app-id, bitable, calendar, drive, lark-cli]
project: "feishuai"
status: solved
date: "2026-09-28"
---

## 现象

一个用应用身份（`tenant_access_token`）读写多维表格、文件夹、日历的 CLI 一直正常。为了接入飞书官方 `lark-cli`，按其引导新建了一个自建应用，然后把 CLI 的 `.env` 里 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 换成了新应用。之后 CLI 所有命令依次报：

```
code=99991672 Access denied. One of the following scopes is required: [bitable:app, bitable:app:readonly, base:record:retrieve]
应用尚未开通所需的应用身份权限
```

给新应用开通 scope 并发布版本后，报错变成：

```
code=91403 Forbidden                      # 读多维表格
code=191002 no calendar access_role       # 读本地配置里记着的 calendar_id
```

用原来配置里的用户 `open_id`（共享成员 / 日程参与人）查通讯录：

```
code=99992361 open_id cross app
```

把用户自己复制出来的多维表格搬进应用新建的文件夹：

```
code=1062524 source parent no permission.
```

另外，本地绑定配置在重新 `init` 时被整体重写，之前写入的 calendar / folder 段丢了，`base_url` 却沿用了旧值（这是自家 CLI 的 bug，另开 issue）。

## 原因

飞书开放平台里三样东西都以**应用**为边界，换 App ID 等于换了一个身份：

1. **scope 按应用申请、按版本发布。** 新应用什么都没开，所以先是 99991672。应用身份（tenant）scope 和用户身份（user OAuth）scope 是两套，`lark-cli` 用户登录拿到一大串用户 scope 不代表应用身份有任何权限。
2. **open_id 按应用隔离。** 同一个人在不同应用下 open_id 不同。旧应用解析出来的 `ou_xxx` 在新应用下就是别人的 / 不存在的 id，接口直接返回 99992361 `open_id cross app`。
3. **资源授权按应用。** 多维表格「添加文档应用」、文件夹协作者、知识库成员都是授权给某个具体应用的；应用主日历也是每个应用一个（`calendar_id` 不同）。新应用对旧应用创建 / 被授权的资源没有任何权限，于是 91403 / 191002。
4. **移动文件要求对源父目录和目标文件夹都有管理权限。** 用户复制到自己个人空间根目录的表格，应用只是表格协作者，个人空间根目录无法授权给应用，所以应用身份搬不动（1062524）。

## 解决方案

换应用（或应用被删重建）后的恢复清单，按顺序做，每步用只读命令验证：

1. **备份本地绑定配置**，再动任何 init 类命令；重新绑定前先用只读的 plan / verify 预览。
2. **给新应用开 scope 并重新发布版本。** 需要哪些看报错里的 `permission_violations`；应用身份常用：`bitable:app`、`docx:document`、`drive:drive:readonly`（保存报告前列文件夹要用）、`space:folder:create` + `space:document:move`（或 `drive:drive`）、`docs:permission.member:create`、`contact:user.id:readonly`、`calendar:calendar` + `calendar:calendar:readonly` + 机器人能力。用户身份的 scope 另外走 OAuth 登录（`lark-cli auth login --scope ...`）。
3. **重新解析 open_id。** 在新应用下重新查（`POST /open-apis/contact/v3/users/batch_get_id` 传手机号；或 `lark-cli contact +search-user --user-ids me`，注意 lark-cli 配置的必须是同一个 App ID），更新所有存 open_id 的地方（共享成员、日程参与人）。
4. **重新授权资源。**
   - 多维表格：在表格里「添加文档应用」→ 新应用 → 可编辑；或者复制一份表由用户自己持有，再把 CLI 绑到新表。
   - 文件夹：让新应用重新创建并授权给用户（`drive/v1/permissions/<folder>/members`，`member_type: openid`）。旧文件夹里的文档手动复制。
   - 日历：重新取新应用主日历（`GET /open-apis/calendar/v4/calendars/primary`），重新写入 `calendar_id` 和参与人。旧应用建的日程仍留在用户日历里，但新应用管不了。
5. **用户自己的文件搬进应用文件夹，要以用户身份搬。** 先让应用把文件夹 full_access 授权给用户，再用 `user_access_token` 调 `POST /open-apis/drive/v1/files/<token>/move`（`lark-cli drive +move --as user --file-token <表 token> --type bitable --folder-token <文件夹 token>`）。用户是文件所有者又有目标文件夹权限，一次成功。

通用建议：

- 把 App ID 当作身份根，**不要原地替换**；接入第二个工具时优先复用同一个应用，或者让两个工具各用各的应用（`lark-cli` 的配置在 `~/.lark-cli/`，与 `.env` 无关），不要把 A 工具的 `.env` 改成 B 工具新建的应用。
- 本地配置里凡是从飞书查回来的 id（open_id、calendar_id、folder_token、app_token）都隐含绑定了 App ID，换应用后全部作废。

## 相关链接

- 99991672 排查：https://open.feishu.cn/document/uAjLw4CM/ugTN1YjL4UTN24CO1UjN/trouble-shooting/how-to-fix-the-99991672-error
- open_id 与应用的关系：https://open.feishu.cn/document/home/user-identity-introduction/open-id
- 移动文件（权限要求）：https://open.feishu.cn/document/server-docs/docs/drive-v1/file/move
- 查询主日历：https://open.feishu.cn/document/server-docs/calendar-v4/calendar/primary
- 官方 lark-cli：https://github.com/larksuite/cli
- 同库相关记录：`common/2026-09-21-feishu-share-email-invalid-use-openid.md`（按手机号换 open_id）
