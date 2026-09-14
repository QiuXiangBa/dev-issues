---
title: "SwiftUI clipShape/clipped 不裁命中区：溢出裁剪框的装饰图在 ZStack 里吞掉遮罩和按钮的点击"
stack: "swift"
platform: [ios]
versions: [xcode 26.6, "ios 18.6 / 26.5 simulator", swiftui]
tags: [swiftui, clipshape, contentshape, hit-testing, zstack, offset, overlay, tap-gesture]
project: "xuejieai"
status: solved
date: "2026-09-14"
---

## 现象

两处同根的表现：

1. 页面 ZStack 里自绘弹层（标签面板）打开时，铺了一层全屏透明遮罩 `Color.clear.contentShape(Rectangle()).onTapGesture { close() }`，弹层放在遮罩之上。弹层本体并不覆盖顶栏按钮，但点顶栏按钮却「没有任何反应」：既不触发遮罩的关闭，也不触发按钮自身的 action。点弹层下方的空白处能正常关闭。
2. 列表里的卡片挂了 `onTapGesture` / `onLongPressGesture`，卡片有一张用 `offset` 铺出去、被卡片圆角裁掉的装饰插画。点卡片上方 30～45pt 的空白，也会触发这张卡的点击。

两处都没有报错，只是「点了没反应」或「点空白处触发了别的东西」。

## 原因

`clipShape` / `clipped` 只裁绘制，不裁 hit-test。子视图用 `offset` / `scaledToFill` / 大于容器的 `frame` 溢出裁剪框后，视觉被裁掉，命中区仍然是子视图的完整 frame。

于是：

- 溢出部分在 ZStack 里压在了兄弟视图（顶栏按钮、透明遮罩、相邻卡片）之上。SwiftUI 命中取最上层的视图，点到一张没有手势的 `Image` 就把事件吞掉了，不会再往下传给遮罩或按钮。
- 挂在容器上的 `onTapGesture` 的命中区 = 容器 frame ∪ 所有子视图的命中区，溢出的插画把容器的可点区扩大了一圈。

复算方法：把溢出子视图的 frame 加 offset 算成父坐标系的矩形，和被「吞掉」的按钮位置对照，重合即是。

## 解决方案

在容器的 `clipShape` 后紧跟同形状的 `contentShape`，把整棵子树的命中区锁回裁剪框：

```swift
ZStack(alignment: .topLeading) {
    background
    Image("decor")
        .resizable()
        .scaledToFill()
        .frame(width: 374, height: 210)
        .offset(x: 8, y: -79)   // 溢出容器
    // ...
}
.frame(width: 320, height: 70)
.clipShape(RoundedRectangle(cornerRadius: 20))
.contentShape(RoundedRectangle(cornerRadius: 20))   // 关键：clipShape 不裁命中区
```

要点：

- `contentShape` 放在容器上、`clipShape` 之后，一处锁整棵子树，比给每张溢出图单独 `.clipped()` 少改地方。
- 纯装饰、永远不响应点击的溢出图也可以直接 `.allowsHitTesting(false)`。
- 排查「点了没反应」时，先看 ZStack 里更上层有没有溢出元素，再怀疑手势本身。
- 修完后每张卡上下边缘外仍各有约 12pt 的命中余量（无插画的卡也一样，上下对称），与溢出无关，原因未查明；量命中区时要把这一圈扣掉，别误判成没修好。

验证手段（本机无 idb）：`xcrun simctl io <udid> screenshot` 截图后按像素列扫描找出视图边缘的精确坐标，再用 CGEvent 合成点击在边缘外 12 / 25 / 40pt 逐点试，比目测靠谱。

## 相关链接

- 项目内修复：PR #215（标签面板横幅）、PR #217（日程卡装饰插画）
- Apple 文档 `contentShape(_:eoFill:)`：定义视图用于 hit-testing 的形状
