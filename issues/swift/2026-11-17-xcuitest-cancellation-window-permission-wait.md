---
title: "XCUITest 权限弹框等待耗尽迟到结果窗口，导致取消测试误报"
stack: "swift"
platform: [ios]
versions: ["Xcode 27.2", "iPadOS 27.0.1", "Xcode 26.6", "iPadOS 15.8.8"]
tags: [xcuitest, xctest, cancellation, permission, timeout, race-condition, test-timing]
project: "ios-ui-testing"
status: solved
date: "2026-11-17"
---

## 现象

在物理 iPad 上验证异步操作取消：测试装配把结果回调延迟 4 秒，测试等待 `late-ready` 事件，再按 Home、离开页面或切换账号，最后检查旧操作没有显示反馈或进入完成态。

后台取消用例出现 `XCTAssertFalse failed`，恢复前台后仍能看到完成按钮，表面上像是 App 的取消逻辑没有挡住迟到结果。但对齐测试操作和应用事件的时间线后发现，结果已经交付并触发完成，测试才按 Home；这次运行没有覆盖到预期的“等待结果时取消”。

本次排查的关键时序，以 `late-ready` 为零点并四舍五入：

| 相对时间 | 事件 |
|---|---|
| 0.00s | 结果就绪，开始延迟交付 |
| 4.04s | `late-delivered`，结果已交付 |
| 4.08s | 旧操作触发完成 |
| 约 5.47s | 测试才执行 Home 操作 |

验证环境为 Xcode 27.2 / iPadOS 27.0.1。这里记录的是测试辅助函数带来的等待副作用，不是认定这些版本存在系统缺陷。

## 原因

通用 HTTP 请求辅助函数同时负责读取测试事件和处理系统权限弹框，结构类似：

```swift
URLSession.shared.dataTask(with: request) { data, response, error in
    // 保存响应后完成 expectation。
    done.fulfill()
}.resume()
allowTestPermissions() // 错放在每次普通事件查询中。
wait(for: [done], timeout: 10)
```

`allowTestPermissions()` 内部调用：

```swift
let alert = XCUIApplication(bundleIdentifier: "com.apple.springboard")
    .alerts.firstMatch
guard alert.waitForExistence(timeout: 1.5) else { return }
// 识别权限类型后点击相应按钮。
```

没有权限弹框时，这个查询仍会等到超时；本次日志中单次调用耗时约 1.5–2 秒。即使 HTTP 请求早已完成、expectation 已被 fulfill，调用方也要先等这段权限查询返回。

等待 `late-ready`、读取截图前后的事件、记录取消前快照等操作都会重复走这个函数。多个隐藏等待叠加，耗尽了 4 秒窗口；与此同时，App 和测试服务的计时器仍在推进。单凭脚本中“先调用取消、再检查完成态”的代码顺序，无法证明实际取消发生在回调之前。

## 解决方案

1. **把权限处理放回预期申请权限的位置。** 在启动或触发首次权限申请时处理对应弹框；普通事件查询只负责请求、解析和有界网络等待，不附带权限弹框轮询。本次修复仅移除了通用 `request()` 中的权限等待，没有修改生产取消逻辑。
2. **先验证测试前提，再验证产品行为。** 取消前确认迟到结果尚未交付；执行 Home 后等待 App 实际进入后台，离页或换账号则确认对应动作生效。动作完成后再次确认结果尚未交付，避免取消动作本身耗尽剩余时间。
3. **记录可核对的时序。** 按同一次操作关联 `late-ready`、`cancel-action-completed`、`late-delivered` 和完成事件。比较时间戳前确认它们使用可比较的时间基准；不能直接相减不同设备或未对齐时钟上的时间。结果事件应在真实交付点记录，事件读取也应有明确的一致性保证。
4. **必须等迟到结果真的交付，再检查无副作用。** 仅在取消后立即看到“没有完成”不够；还要确认迟到回调已经抵达，并检查没有旧操作反馈、完成或页面推进。对异步更新，应给出有界观察时间或明确的处理完成信号。

以下是测试结构示意，`waitEvent`、`hasEvent`、`recordEvent`、`waitUntilBackgrounded` 和 `assertNoOldResultEffects` 是测试自有辅助函数，并非 XCTest API；事件查询不得再混入权限等待：

```swift
continueAfterFailure = false
try waitEvent("late-ready")
XCTAssertFalse(try hasEvent("late-delivered"))

XCUIDevice.shared.press(.home)
try waitUntilBackgrounded(app) // 接受 .runningBackground 与 .runningBackgroundSuspended
try recordEvent("cancel-action-completed")
XCTAssertFalse(
    try hasEvent("late-delivered"),
    "Cancellation must precede the delayed result"
)

try waitEvent("late-delivered")
app.activate()
try assertNoOldResultEffects()
```

示意代码要求测试装配在 App 后台时仍能交付迟到结果；如果装配要恢复前台才能继续运行，应先恢复，再等待交付事件。无论哪种方式，都要核对实际事件顺序，不能把“回调未运行”当作取消成功。

后台状态要同时接受 `.runningBackground` 和 `.runningBackgroundSuspended`。iPadOS 15.8.8 真机上按 Home 后，XCTest 日志显示应用直接从 Running Foreground 变为 Running Background Suspended，只等 `.runningBackground` 会在取消前提处误报。用 `XCTNSPredicateExpectation` 包一个读取 `app.state` 的 block 谓词同样失败：状态约 1.5 秒已变化，期望仍在 2 秒时超时，原因未查明。最终改为先 `app.wait(for: .runningBackgroundSuspended, timeout: 2)`，未命中再检查当前状态是否为 `.runningBackground`，并把实际状态记入事件日志。注意这个等待本身也计入迟到窗口：应用若停留在 `.runningBackground`，前一步会等满超时，要为此预留时间，或换成对两种状态都能及时返回的等待。

若取消前或动作后的前提断言失败，应先排查测试调度和辅助函数耗时，不能直接把后续完成态归因于生产取消缺陷。单纯增大迟到延迟可能暂时让测试变绿，但不能替代移除隐藏等待和检查事件顺序。

## 验证结果

移除普通事件查询中的权限等待、补齐取消前后断言后，重跑两个页面入口下的后台、离页、换账号共 6 组用例。取消动作完成均早于迟到交付约 2.53–3.45 秒，旧操作完成事件均为 0，取消后的反馈检查通过。原失败日志与修复后结果均保留在本地验收证据中。

之后在 iPadOS 15.8.8 真机（Xcode 26.6 构建的测试 runner）上，按上述方式修正后台状态判定后复验同样 6 组，均通过：两个后台用例实际记录的状态都是 Running Background Suspended，取消动作完成早于迟到交付约 3.47–4.72 秒。

验证的是受控迟到回调下的客户端取消行为。取消前可能已经发生上传，不能把“取消后没有继续上传或完成”写成“该操作从未上传”。上述时间差是本轮测量值，不是其他设备的固定性能保证。

## 相关链接

- [Apple：XCUIElement.waitForExistence(timeout:)](https://developer.apple.com/documentation/xcuiautomation/xcuielement/waitforexistence(timeout:))
- [Apple：Asynchronous Tests and Expectations](https://developer.apple.com/documentation/xctest/asynchronous-tests-and-expectations)
