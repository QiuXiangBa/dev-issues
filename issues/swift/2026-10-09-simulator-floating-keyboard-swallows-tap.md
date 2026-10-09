---
title: "iPad 模拟器浮动键盘开着时，XCUITest 点页面按钮第一下被吞掉、动作不触发"
stack: "swift"
platform: [ios]
versions: [xcode 27.0, ios 18.6, ipad simulator, xcuitest]
tags: [xcuitest, ios-simulator, ipad, keyboard, floating-keyboard, ui-testing, tap]
project: "tutuai"
status: workaround
date: "2026-10-09"
---

## 现象

iPad 模拟器上跑 XCUITest：在手机号输入框（`keyboardType(.numberPad)`）里输完 11 位，紧接着 `app.buttons["获取验证码"].tap()`。按钮已经可点（`isEnabled == true`），但动作没触发（倒计时没开始），浮动数字键盘反而收起了。

- 有一次运行里 `send.isHittable` 报 `false`，另一次报 `true`，两次动作都没触发。
- 想用键盘自己的收起键收：`app.buttons["Hide keyboard"]` 在元素树里能查到，但 frame 在屏幕外（x 为负），`tap()` 报 `Failed to scroll to visible (by AX action) ... kAXErrorCannotComplete`。

当时正在改这个按钮的样式。把样式改回原版本、用同样的步骤对照跑了一次，结果相同，说明问题和按钮实现无关。

## 原因

数字键盘在 iPad 模拟器上以浮动小键盘的形式出现。键盘开着时，点键盘以外的位置，第一下被键盘一侧消费掉（收起键盘），没有传到 App 的按钮上。真机手动操作是否同样如此没有验证；这里只确认了模拟器 + XCUITest 下的行为，且与被测按钮的实现无关。

## 解决方案

点按钮之前先把键盘收掉，再点：

```swift
// 输完手机号后：点页面空白处收键盘（页面背景上挂了 onTapGesture { focusedField = nil }）
app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: 60, dy: 650)).tap()
usleep(1_500_000)
XCTAssertTrue(send.isHittable)
send.tap()   // 这次动作触发，倒计时开始
```

- 页面没有「点空白收键盘」时，可以在测试里点一个不会触发任何动作的区域，或者给测试入口加一个收起焦点的办法。
- 别依赖 `app.buttons["Hide keyboard"]`：浮动键盘下它在屏幕外，点不到。
- 测「键盘开着时直接点按钮」这类交互，要用改动前的版本做对照，先确认是不是测试环境本身的行为，再判断是不是回归。

附：输入框挂在带 `onTapGesture { focusedField = ... }` 的容器里、键盘弹起时页面会上移的，`textField.tap()` 后 `textField.typeText(...)` 可能报 `Neither element nor any descendant has keyboard focus`。改用 `app.typeText(...)`（向当前焦点输入），并确认焦点确实落在目标框上：页面上移后各输入框的 frame 会变，按旧坐标点可能落到别的框。

## 相关链接

- https://developer.apple.com/documentation/xctest/xcuielement/typetext(_:)
