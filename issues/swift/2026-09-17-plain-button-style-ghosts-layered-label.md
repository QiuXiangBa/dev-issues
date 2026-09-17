---
title: "SwiftUI 分层绘制的按钮用 .plain 样式按下出现重影"
stack: "swift"
platform: [ios]
versions: [xcode 27.0, ios 18.6, ipados 26.3.1, swiftui]
tags: [swiftui, button, buttonstyle, plain, opacity, ghosting]
project: "tutuai"
status: solved
date: "2026-09-17"
---

## 现象

自绘的「实体键」风格圆钮：label 是一个 ZStack，底层一枚深色圆向下 `offset(y: 6)` 当底边，上层一枚浅色圆当面，再叠白色图标。按钮用 `.buttonStyle(.plain)`。

在 iPad 真机上按住按钮时，面变得半透明，透出下面偏移的底边圆，看起来像两个错位的圆叠在一起（重影）；松开恢复。模拟器上也能复现，只是不明显。

## 原因

`.plain` 不是「无样式」。iOS 上它的按压反馈是把整个 label 降到约 50% 不透明度（`PlainButtonStyle` 在 `isPressed` 时对 label 应用 opacity）。

label 只有一层时看不出问题；label 内部分层且各层错位时，透明度一降，下层原本被完全遮住的部分就透出来，形成重影。任何「主色块 + 偏移底边」「卡片 + 投影色块」之类的分层 label 都会中招。

## 解决方案

不用 `.plain`，写一个 `ButtonStyle`，按压反馈不改透明度，改用位移或缩放：

```swift
struct PressDownButtonStyle: ButtonStyle {
    let face: Color
    let lip: Color
    let diameter: CGFloat

    func makeBody(configuration: Configuration) -> some View {
        let drop: CGFloat = configuration.isPressed ? 6 : 0
        ZStack {
            configuration.label   // 只保留命中区（Color.clear + contentShape）
            Circle().fill(lip)
                .frame(width: diameter, height: diameter)
                .offset(y: 6)
            Circle().fill(face)
                .frame(width: diameter, height: diameter)
                .offset(y: drop)  // 按下时面沉到底边上
        }
        .animation(.easeOut(duration: 0.08), value: configuration.isPressed)
    }
}

Button(action: action) {
    Color.clear
        .frame(width: size, height: size + 4)
        .contentShape(Rectangle())
}
.buttonStyle(PressDownButtonStyle(face: .green, lip: .init(white: 0.3), diameter: size - 4))
```

要点：

- 把绘制放进 `ButtonStyle.makeBody`，label 只留命中区，这样样式能拿到 `isPressed` 来驱动位移。
- 如果只想去掉透明度反馈、不想重画，也可以让 `makeBody` 直接返回 `configuration.label.scaleEffect(configuration.isPressed ? 0.95 : 1)`，同样不会透出下层。
- 单层图片按钮（一张导出图当 label）用 `.plain` 没问题，透明度变化不会产生错位。

## 相关链接

- Apple 文档 `PlainButtonStyle`：https://developer.apple.com/documentation/swiftui/plainbuttonstyle
- 项目内实现：tutuai-app `ios/Sources/Pad/DailyTask/PadDailyTaskWidgets.swift` 的 `PadDailyRoundButtonStyle`
