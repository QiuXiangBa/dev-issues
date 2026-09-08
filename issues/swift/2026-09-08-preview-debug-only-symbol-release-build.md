---
title: "#Preview 引用 #if DEBUG 符号导致 Release 构建失败"
stack: swift
platform: [ios]
versions: [xcode 26.6, ios 16.0 deployment target]
tags: [swiftui, preview, release-build, xcodebuild, debug-macro]
project: xuejieai
status: solved
date: 2026-09-08
---

## 现象

SwiftUI 视图文件里的示例数据放在 `#if DEBUG` 里，`#Preview` 块引用了它。Debug 配置下模拟器构建正常，PR Self-Review 时跑 Release 构建报错：

```
error: cannot find 'sampleMessages' in scope
```

报错位置就在 `#Preview { ... }` 内部。

## 原因

`#Preview` 是宏，展开后的代码在所有构建配置下都会参与编译，并不会因为是 Release 就被剥掉。而示例数据只在 `#if DEBUG` 里声明，Release 下符号不存在，编译失败。

平时只跑 Debug 构建和模拟器预览，所以这个错误只会在 Release / Archive 时暴露。

## 解决方案

把整个 `#Preview` 也包进 `#if DEBUG`：

```swift
#if DEBUG
extension ChatMessage {
    static let sampleMessages: [ChatMessage] = [...]
}

#Preview {
    ChatView(messages: ChatMessage.sampleMessages)
}
#endif
```

并把 Release 构建加进 PR 验证清单，Debug 通过不代表 Release 通过：

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
xcodebuild -project App.xcodeproj -scheme App -configuration Release \
  -destination 'id=<模拟器 UDID>' build
```

附带一个坑：`-destination 'name=iPhone 16 Pro'` 在本机匹配不到设备，用 `xcrun simctl list devices` 取 UDID 后写 `id=<UDID>` 更稳。

## 相关链接

- https://developer.apple.com/documentation/swiftui/previews-in-xcode
