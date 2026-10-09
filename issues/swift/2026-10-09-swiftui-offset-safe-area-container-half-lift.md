---
title: "SwiftUI 对 ignoresSafeArea 的 GeometryReader 容器整体 offset 做键盘避让，容器被拉高重新居中，上移量只生效一半"
stack: "swift"
platform: [ios]
versions: [xcode 27.0, "ios 18.6 simulator", swiftui]
tags: [swiftui, keyboard, keyboard-avoidance, offset, geometryreader, ignoressafearea, safe-area, scaleeffect]
project: "tutuai"
status: solved
date: "2026-10-09"
---

## 现象

场景页用「固定设计画布等比缩放」的容器（下称画布容器）：

```swift
GeometryReader { geo in
    let scale = min(geo.size.width / base.width, geo.size.height / base.height)
    ZStack {
        background()
        content()
            .frame(width: base.width, height: base.height)
            .scaleEffect(scale)
            .position(x: geo.size.width / 2, y: geo.size.height / 2)
    }
    .clipped()
}
.ignoresSafeArea()
```

页面里有输入框，键盘弹起时在外层对整个画布容器 `.offset(y: -lift)` 上移，`lift` 按「某一行的下缘高出键盘 20pt」计算。

- 实际只上移了大约一半。iPad Air 11″ 横屏、软键盘高 422pt：算出的 `lift = 420pt`，屏幕上只动了约 209pt。错误提示行、提交按钮全被键盘盖住；XCUITest 里按钮 `isHittable = false`，点按钮实际点到了键盘按键。没有任何报错。
- 用 Simulator.app 手测时常连着硬件键盘（只显示快捷栏），`lift` 很小，看不出问题。`xcrun simctl boot` headless 启动（不开 Simulator.app）才会出完整软键盘。

## 原因

在画布容器内部的 GeometryReader 里打日志（`geo.size`、`geo.frame(in: .global)`）：

| 时刻 | size | global origin y |
|---|---|---|
| 键盘未弹起 | 1180×820 | 0 |
| 外层 offset 上移 420 后 | 1180×1240.37 | −420 |

带 `.ignoresSafeArea()` 的视图会把自己的 frame 延伸到安全区（含键盘区）的边缘。整体被 offset 上移后，它为了仍然铺到屏幕底，把自己拉高了 `lift`；内容又按 `geo.size.height / 2` 居中，于是往下沉回 `lift / 2`。外层的 offset 和内层的重新居中抵消了一半。

（现象和日志是实测的；「offset 后安全区按新位置重算」这一机制是根据日志推断的。）

## 解决方案

不要移动画布容器本身，把位移放进它的 content 里。content 是先 `frame` 到设计尺寸、再 `scaleEffect` 的，所以位移要换成设计单位：

```swift
GeometryReader { geo in
    let scale = min(geo.size.width / base.width, geo.size.height / base.height)
    // 没有键盘不动（静止时不留亚像素位移）；scale 为 0 的那一轮也不动（下面要除以它）
    let lift = keyboardHeight > 0 && scale > 0
        ? max(0, anchorBottom + 20 - (geo.size.height - keyboardHeight)) : 0
    CanvasContainer(base: base) {
        background
    } content: {
        ZStack {
            canvas
                .offset(y: -lift / scale)   // 设计单位；scaleEffect 之后屏幕位移 = lift
                .animation(.easeOut(duration: 0.25), value: lift)
            toast                           // 不跟着上移的浮层放成同层兄弟
        }
    }
}
.ignoresSafeArea()
```

要点：

- 容器本身一行不用改，其它页面不受影响。
- 上移后画布底部会露出来，半透明的键盘会透出背景色：把底部的底色块往下多画一截（至少最大上移量）。
- 上移量真正生效后，要在最矮的机型（如 iPad mini 横屏）上复查顶部输入框有没有被推出屏幕。锚点别取得太靠下：锚在提交按钮下缘，不要锚在按钮下方的提示行。
- 验证：headless 启动模拟器出软键盘；XCUITest 断言目标元素 `frame.maxY <= app.keyboards.element.frame.minY`，以及按钮 `isHittable`。注意 `keyboards.element.frame` 不含快捷栏，比 `keyboardWillChangeFrameNotification` 给的 frame 矮约 55pt。
- Android Compose 的同类写法在布局摆放阶段 `placeable.place(0, -lift)`，不经过安全区计算，没有这个问题。

## 相关链接

- 项目内修复：PR #325
