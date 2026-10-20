---
title: "账号恢复失败后跳转登录入口导致自动重登循环"
stack: "wechat-mp"
platform: [wechat]
versions: ["微信开发者工具 Stable 2.02.2608060", "微信基础库 3.17.4", "Node.js 24.20.0"]
tags: [auth, session, 401, recovery, navigation, retry, promise]
project: "wechat-miniprogram"
status: solved
date: "2026-10-20"
---

## 现象

小程序通过统一账号入口完成会话恢复，再进入业务 Tab。某个业务 GET 请求返回 401 后，自动恢复并重试一次，但恢复得到的凭证又被接口拒绝：

```text
业务 GET → 401 → 静默恢复 → 进入 Tab
         → 重试 GET 再次 401 → 返回账号入口
         → 入口 onLoad 再次静默登录 → 进入 Tab → ……
```

请求封装已经限制 GET 最多重试一次，仍不能阻止页面跳转触发新一轮登录。首次启动也存在时序边界：App.onLaunch 的恢复任务如果在入口挂载前失败，入口 onLoad 重新调用恢复函数，会额外自动登录一次。

## 原因

1. 请求重试次数只约束一次请求，入口页面重建后会开启新的请求及登录流程，形成跨页面的循环。
2. 只保存进行中的 Promise，在 finally 中清空，不能保留“自动恢复已经失败”的结果。
3. 错误状态若只存在于被销毁的页面中，wx.reLaunch 后会丢失。入口无法区分首次进入、自动恢复失败和用户主动重试。

## 解决方案

在 App 或独立会话服务中同时维护：进行中的恢复任务、最近一次失败、账号就绪状态。错误状态需要跨页面保留，但不必永久写入本地存储。

- 所有启动调用共享同一份进行中的恢复任务。
- 初始恢复失败、自动恢复失败，以及自动恢复后的凭证再次被拒绝，都保留错误结果。
- 返回账号入口时默认读取该结果，显示失败和“重试”，不隐式开启下一轮登录。
- 只有用户明确点击重试，才清除失败结果并开始新的恢复操作。
- 会话变更后，旧凭证的迟到 401 或旧恢复任务的响应不能清除、覆盖较新的账号状态。结合凭证匹配与会话版本号检查。
- GET 仍最多自动重试一次；写操作不自动重放。

以下为恢复状态管理的示意代码，restoreSession 代表应用自己的恢复实现；HTTP 401 的处理也必须把最终恢复失败写入同一份 recoveryError：

```js
let pending = null
let recoveryError = null

function prepareSession({ manualRetry = false } = {}) {
  if (manualRetry) recoveryError = null
  if (recoveryError) return Promise.reject(recoveryError)
  if (pending) return pending

  const task = Promise.resolve()
    .then(() => restoreSession())
    .catch((err) => {
      recoveryError = err
      throw err
    })
    .finally(() => {
      if (pending === task) pending = null
    })
  pending = task
  return task
}
```

不能只在入口页展示错误却让 onLoad 始终调用一次全新的静默登录；也不能只增加请求重试计数而忽略导航触发的恢复。

## 验证

使用实际页面方法、会话服务及请求封装，在内存集成脚本和 node:test 中模拟响应：

1. 首次 401 → 恢复成功 → 同一 GET 再次 401：入口显示错误，wx.login 调用次数不继续增加。
2. 自动恢复本身失败：入口重建后不隐式再次登录。
3. App.onLaunch 的任务在入口挂载前失败：入口仍展示同一失败结果。
4. 用户点击重试：开启一份新任务；快速重复点击不会产生并行恢复。
5. 旧会话响应晚到：不覆盖新的绑定结果。

以上为应用层集成回归结果；不代表已完成真实手机号授权或所有微信客户端版本的验证。

## 相关记录

- [账号门禁与资源清理](2026-10-20-auth-gate-resource-cleanup.md)
