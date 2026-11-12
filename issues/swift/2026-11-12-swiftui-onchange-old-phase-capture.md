---
title: "SwiftUI 单参数 onChange 回读旧 scenePhase，导致前后台状态反转"
stack: "swift"
platform: ["ios"]
versions: ["iOS 27.0.1", "Xcode 27.1"]
tags: ["swiftui", "onchange", "scenephase", "lifecycle", "stale-capture"]
project: "<sample-project>"
status: "solved"
date: "2026-11-12"
---

## 现象

应用从系统弹窗或后台返回后，页面可操作，控制器却仍保存 `isActive=false`，前台操作被守卫拒绝。界面只显示“操作暂不可用”等通用提示，容易被误判为远端配置或商品缓存问题。

可疑结构是：单参数 `onChange` 收到新值后丢弃它，调用捕获当前 View 的 helper，helper 再读取 `@Environment`：

```swift
.onChange(of: scenePhase) { _ in
    connectController()
}

private func connectController() {
    controller.update(isActive: scenePhase == .active)
}
```

定位时只记录必要标量：调用入口、回调传入的新 phase、传给控制器的布尔值，以及操作守卫最终读到的值。不要为排查生命周期而打印整个账号对象、认证材料或交易载荷。

## 原因

问题出在把回调参数与捕获 View 中的环境值混用。对 `onChange(of:perform:)`，Apple 明确说明系统向 action 传入**变化后的新值**；重新读取闭包捕获的 View 并不能替代这个参数。[Apple 官方说明](https://developer.apple.com/documentation/swiftui/view/onchange(of:perform:).md)

本次真机复现中，新事件已经表示回到前台，helper 回读的 phase 仍是先前状态，随后又将控制器覆盖成非前台。MainActor 会串行执行同步片段，但不会把已经捕获的值自动换成另一个事件的新值。

“界面按钮可点击”也不能证明控制器的独立缓存正确。若按钮可用性未依赖该缓存，直到真正执行操作时才会被前台守卫拦截。诊断应区分缓存缺失、配置拒绝和前台状态拒绝等不同分支，不能只依据它们共用的用户文案判断。

## 解决方案

显式传递回调的新值，让 helper 只使用参数生成前台标志：

```swift
.onChange(of: scenePhase) { newPhase in
    connectController(phase: newPhase)
}

private func connectController(phase: ScenePhase) {
    controller.update(isActive: phase == .active)
}
```

初始连接等其他入口也要明确传入对应 phase，检查所有写入 `isActive` 的位置；控制器应先更新前台标志，再恢复等待前台的操作。保留操作前的前台检查、账号作用域检查及必要的配置重查。

本修复继续使用原单参数 API，适用于需要兼容旧部署目标的代码。若改用其他 `onChange` 重载，应重新核对其可用系统版本与闭包语义，不能把不同重载混为一谈。

### 验证与边界

- 在真实设备执行 active → inactive → active 循环，并在实际操作边界确认控制器最后读到 `true`；本次该运行检查已通过。
- 诊断同时确认其他前置条件有效，避免把不同拒绝分支误算成前台问题。
- 当时的完整单测 64 项、Release 编译及两档提示/导航 UI 测试通过；后两者不直接证明真实 Root → Controller 的生命周期桥接。
- 直接在测试替身里修改 `Context.isActive` 不能覆盖 View 是否正确转发 phase。真实后台操作拒绝和完整系统事件链仍应分别检查，不以单一布尔测试代替。

这条与“启动首次账号就绪误清提示”属于不同根因：后者是观察缓存与提示失效规则，不能用它的修复替代 phase 转发。

## 相关链接

- [Apple：onChange(of:perform:) Markdown 文档](https://developer.apple.com/documentation/swiftui/view/onchange(of:perform:).md)：单参数 action 接收变化后的新值，官方 scenePhase 示例直接使用该参数。
- [相关：启动首次就绪与提示失效规则](2026-11-11-swiftui-bootstrap-notice-account-scope-race.md)。
