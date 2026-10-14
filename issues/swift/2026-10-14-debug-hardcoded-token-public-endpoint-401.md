---
title: "Debug 构建硬编码的调试 token 过期后，公开接口（发码 / 登录）也返回 401"
stack: swift
platform: [ios]
versions: [xcode 27.0, ios 16.0+, swift 5.0, spring boot backend]
tags: [auth, 401, authorization-header, debug, hardcoded-token, urlsession, spring]
project: xuejieai
status: solved
date: 2026-10-14
---

## 现象

Debug 构建的 App 调「发送短信验证码」「验证码登录」这类不需要登录的公开接口，统一返回 HTTP 401：

```json
{"success":false,"code":401,"msg":"未经授权 需要提供有效的身份验证信息"}
```

Release 构建正常。用 curl 按接口文档重放同样的请求体、不带 `Authorization` 头也正常（200）。Keychain 里没有登录 token（已登出），所以也不是残留 token 的问题（那是另一条记录）。

## 原因

客户端网络层组装请求时，为了联调方便，在 `#if DEBUG` 下给「没有本地 token」的请求兜底塞了一个写死的会话 token：

```swift
if authorized, let token = tokens.token, !token.isEmpty {
    request.setValue(token, forHTTPHeaderField: "Authorization")
} else {
    #if DEBUG
    request.setValue("<某次登录拿到的会话 token>", forHTTPHeaderField: "Authorization")
    #endif
}
```

两个因素叠加：

1. 公开接口的调用传的是 `authorized: false`，正好也落进 else 分支，所以发码 / 登录请求在 Debug 下同样带上了这个头。
2. 后端（Spring）的鉴权过滤器对所有请求统一处理：只要 `Authorization` 头**存在**就校验，无效直接 401，不区分接口是否公开；不带头的请求才放行到业务逻辑。

写死的 token 是某次登录的会话凭证，几周后过期 / 被登出作废，于是 Debug 包所有请求（包括公开接口）一起 401。Release 不编译这段代码所以正常。引入提交和出问题隔了近两个月，现象看起来像后端或账号问题，很难直接联想到客户端。

## 解决方案

删掉兜底分支：没有 token 就不发 `Authorization` 头，公开接口按公开接口走，受保护接口如实 401 触发登录拦截。

```swift
if authorized, let token = tokens.token, !token.isEmpty {
    request.setValue(token, forHTTPHeaderField: "Authorization")
}
```

真需要固定 token 联调时，走不入库的配置（Xcode Scheme 环境变量 / xcconfig），不要写进源码：会话凭证进 git 既是安全问题，也注定会过期。

排查方法（任何客户端通用）：

1. 用 curl 按接口文档重放请求，**不带** `Authorization` 头 → 200，说明后端和参数都没问题。
2. 同一请求加一个随便的 `Authorization: xxx` → 401，说明后端对公开接口也校验该头。
3. 回到客户端找所有设置 `Authorization` 的地方（`grep -rn 'forHTTPHeaderField: "Authorization"'`），特别留意 `#if DEBUG` 块和「没有 token 时」的分支。

## 相关链接

- 同为 401 但根因不同的记录：`issues/swift/2026-09-08-simulator-keychain-token-persists.md`（Keychain 残留的 mock token）
