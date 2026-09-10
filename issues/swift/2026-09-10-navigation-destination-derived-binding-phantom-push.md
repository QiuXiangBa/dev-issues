---
title: "navigationDestination(isPresented:) 绑派生 Binding 导致 pop 后再 push 一页空白页"
stack: "swift"
platform: [ios]
versions: [ios 16.0 deployment target, ios 18.6 simulator, xcode 26.6]
tags: [swiftui, navigationstack, navigationdestination, binding, state, pop, flash]
project: "xuejieai"
status: solved
date: "2026-09-10"
---

## 现象

列表页用 `navigationDestination(isPresented:)` push 编辑页，`isPresented` 是从一个 Optional 状态派生的自定义 Binding：

```swift
@State private var editingItem: Item?

.navigationDestination(isPresented: Binding(
    get: { editingItem != nil },
    set: { if !$0 { editingItem = nil } }
)) {
    if let item = editingItem {
        EditorView(item: item).id(item.id)
    }
}
```

编辑页点返回（`dismiss()`）或侧滑返回后，列表页出现约 0.5s，**又被 push 出一页带系统「Back」栏的空白页**，停留约 0.5s 再自动 pop 回列表。用户描述为「返回时中间有个页面切了一下」。

模拟器录屏按 30fps 抽帧：2.27～2.53s 正常 pop；2.97～3.40s 空白页从右侧滑入；3.50～3.73s 空白页自动 pop。

在 Binding 的 get / set、destination 闭包、目的页 `onAppear` / `onDisappear` 加 `print`，pop 时的调用顺序是：

```
isPresented set <- false        ← editingItem = nil 已写
isPresented get -> true         ← 紧接着回读却仍是 true
destination body editingItem=37CC…
editor onAppear 37CC…           ← 目的页被再 push 一次
isPresented get -> false
destination body editingItem=nil   ← if let 失败 → EmptyView（空白页 + 系统导航栏）
editor onDisappear ×2
```

## 原因

SwiftUI 处理 pop 时先对 `isPresented` 调 `set(false)`，然后**立刻回读** `wrappedValue` 确认状态。派生 Binding 的 get 读的是 `editingItem != nil`，而 `set` 里对 `@State` 的写入此时尚未落地，回读得到过期的 `true`，SwiftUI 据此认为目的页仍应在栈上、重新 push 了一次。等 `nil` 真正落地，destination 闭包里的 `if let` 变成 `EmptyView`（没有 `.toolbar(.hidden)`，所以露出系统导航栏和「Back」），随后 `isPresented` 为 false 又把它 pop 掉。

直接绑 `@State` 布尔（`$isPresented`）时 SwiftUI 读写的是同一份 State 存储，不存在这个回读时差。

## 解决方案

开关用独立的 `@State` 布尔，Optional 只负责给目的页喂数据，退出后**不清空**（顺带避免 pop 动画过程中目的页变成空视图）：

```swift
@State private var isEditing = false
@State private var editingItem: Item?      // 退出后保留，不置 nil

.navigationDestination(isPresented: $isEditing) {
    if let item = editingItem {
        EditorView(item: item).id(item.id)   // 身份跟数据走，第二次进不同条目时 @State 才会重建
    }
}

// 打开时两者一起置
editingItem = item
isEditing = true
```

部署目标 iOS 16 用不了 iOS 17 的 `navigationDestination(item:)`；能用 iOS 17+ 的项目直接用 `item:` 版本也可以。

排查这类「返回闪一下」的问题，靠截图抓不到；用 `xcrun simctl io <udid> recordVideo` 录屏，`AVAssetImageGenerator` 按 30fps 抽帧，按相邻帧 PNG 大小差筛出变化段，再拼缩略图看，能精确到哪一帧多 push 了页面。

## 相关链接

- 项目内修复：https://github.com/QiuXiangBa/xuejieai-app/pull/201
- 同类坑（destination 急切求值）：`swift/2026-09-08-navigationlink-destination-eager-init.md`
