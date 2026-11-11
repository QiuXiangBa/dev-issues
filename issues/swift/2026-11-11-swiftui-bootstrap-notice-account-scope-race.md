---
title: "SwiftUI 启动时账号已就绪但 onChange 尚未更新，误清同作用域事件提示"
stack: "swift"
platform: [ios]
versions: ["Xcode 27.1 (27A9275)", "Apple Swift 6.4 (swiftlang-6.4.0.34.1)", "iOS Simulator 26.5 (23F77)"]
tags: [swiftui, onchange, bootstrap, async, account-scope, notice, race-condition]
project: "general"
status: solved
date: "2026-11-11"
---

## 现象

SwiftUI 启动时，系统回调或应用外事件的结果已经发布到共享控制器，但全局提示没有出现，也没有崩溃或网络错误。给 DEBUG 夹具增加“先重新连接控制器，再发布提示”后，界面测试可能通过，生产中的异步事件仍有被清掉的窗口。

常见结构是：

- AppState 保存当前账号、就绪状态和账号作用域 `scope`。
- 控制器通过闭包动态读取 AppState 的最新值。
- Root 用 `onChange` 重新连接控制器；控制器另外缓存 `lastAccount`、`lastScope`。
- 一旦缓存与当前值不同，就同时触发状态补扫和清空事件提示。

错误条件示意：

```swift
let accountChanged = account != lastAccount || scope != lastScope
if accountChanged { notice = nil }
```

在同一作用域首次加载账号时，`nil → A` 也满足这个条件，会把已经属于 A 的新提示误当成旧账号残留。

## 原因

**动态读取到的就绪状态，不等于视图观察回调维护的缓存已经同步。** 一种会触发问题的交错如下；它不是对 SwiftUI 固定帧顺序的假设：

1. 当前作用域为 S，控制器上次观察到的账号仍是 `nil`。
2. 启动加载完成，AppState 的账号变为 A、就绪状态变为 true。
3. 事件处理通过动态闭包读到最新的 A，快速异步校验完成后发布提示 N。
4. Root 的 `onChange` 随后执行，重新连接控制器。
5. 控制器看到 `lastAccount=nil`、当前账号为 A，按“账号有变化就清提示”删除 N。

这里闭包没有读到旧账号；滞后的是控制器的“上次观察值”。错误在于把“第一次从未就绪变为就绪”与“已有账号被替换”共用同一种清理规则。

Apple 将 `onChange` 定义为值变化时执行副作用的修饰器。该语义不能当作多个异步任务、动态读取闭包与应用缓存之间的业务原子事务；上述窗口来自应用自己的两套状态。即使快速操作中包含一次 `await`，也不能据此假设视图观察缓存一定先更新。

## 解决方案

把**状态补扫条件**与**提示失效条件**分开：

- 状态补扫仍可在 `nil → A` 时执行，避免漏掉启动时尚未处理的事件。
- 提示只在作用域变化，或已有非空账号被替换/清空时删除。
- 同一作用域的首次 `nil → A` 仅代表启动就绪，不清除此时已经发布的提示。

将提示清理规则提取成生产代码实际使用的纯谓词，再直接回归该谓词：

```swift
func shouldClearNotice(
    previousAccount: String?, previousScope: UUID?,
    account: String?, scope: UUID?
) -> Bool {
    scope != previousScope
        || (previousAccount != nil && account != previousAccount)
}
```

连接逻辑分别应用两个条件，最后更新观察缓存：

```swift
let needsRefresh = account != lastAccount || scope != lastScope
if shouldClearNotice(
    previousAccount: lastAccount, previousScope: lastScope,
    account: account, scope: scope
) {
    notice = nil
}
lastAccount = account
lastScope = scope
if needsRefresh { refreshForCurrentSession() }
```

`scope` 是应用在显式换号、恢复或重建会话时推进的代际标识，不是每次界面刷新都生成的新值。事件在账号尚未就绪时也应捕获当前 scope；异步操作完成前后检查同一 scope，避免旧操作使用后续账号。

| 上次账号 | 当前账号 | scope | 是否清提示 |
|---|---|---|---|
| nil | A | 相同 | 否，首次就绪 |
| A | A | 相同 | 否，重复观察 |
| A | B | 相同 | 是，已有账号变化 |
| A | nil | 相同 | 是，已有账号被清空 |
| 任意 | 任意 | 改变 | 是，旧作用域失效 |

### 验证范围

本次全量 64 项单元测试通过、无跳过，其中 4 项直接执行生产共用的提示清理谓词，覆盖上表的首次就绪、重复观察、换号/清空和换 scope。

界面验证使用 iPhone SE（第三代）与 Pro Max 两档尺寸上的原有事件提示夹具，检查全局提示及后续交互。夹具只验证展示和路由，不等于真实应用外事件链路，也不证明某一种调度顺序一定发生。不能靠 DEBUG 中“先连接后注入”的排序代替生产失效规则修复；单元回归必须独立于该夹具执行。

工具链与模拟器版本来自实际命令输出。此解法针对应用状态机语义，不声称所有系统版本具有完全相同的视图调度时序。

## 相关链接

- [Apple：onChange(of:perform:)](https://developer.apple.com/documentation/swiftui/view/onchange(of:perform:))：值变化时触发副作用，并向闭包传入新值。它不是对应用多个观察缓存更新顺序的约定。
