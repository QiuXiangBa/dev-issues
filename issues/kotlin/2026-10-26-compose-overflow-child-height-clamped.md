---
title: "Compose 子元素要溢出父容器时 height() 被父约束压扁：改用 wrapContentHeight(unbounded = true)"
stack: "kotlin"
platform: [android]
versions: ["compose-bom 2025.06.00 (ui 1.8.2)", "kotlin 2.1.20", "agp 8.11.1"]
tags: [compose, layout, constraints, overflow, wrapcontentheight, unbounded, zstack, swiftui-port]
project: "xuejieai"
status: solved
date: "2026-10-26"
---

## 现象

设计稿 / SwiftUI 里一张 116 高的卡片，内部有一张从 37 起、高 87 的内层卡（37 + 87 = 124 > 116，内层卡越过外层底边 8）。SwiftUI 的 `ZStack` 不裁子视图，直接溢出，视觉正确。

Compose 照写：

```kotlin
Box(Modifier.fillMaxWidth().height(116.dp)) {
    InnerCard(Modifier.align(Alignment.TopCenter).padding(top = 37.dp).fillMaxWidth())  // 内部 Modifier.height(87.dp)
}
```

内层卡没有溢出，而是被压成 79 高；里面两行摘要只剩一行加省略号。没有任何报错或警告。

## 原因

Compose 的 `Modifier.height(x)` / `size(x)` 是「在父约束范围内」要求尺寸：父给的 `maxHeight` 是 116 − 37 = 79，`height(87)` 会被夹到 79（`SizeModifier` 的 `enforceIncoming = true`）。父容器不会像 SwiftUI 那样让子视图按自己的理想尺寸排版再溢出。

`requiredHeight(87)` 能拿到 87，但超出父约束的部分会被**居中**放置（上下各溢出 4），不是从顶部向下溢出。

## 解决方案

在子元素前面放开高度约束，并指定对齐方向：

```kotlin
InnerCard(
    Modifier
        .align(Alignment.TopCenter)
        .padding(top = 37.dp)
        .fillMaxWidth()
        .wrapContentHeight(align = Alignment.Top, unbounded = true),  // 子元素按自己的 height(87) 量，顶对齐，向下溢出
)
```

`wrapContentHeight(unbounded = true)` 把传给子元素的 `maxHeight` 改成无限，子元素测出 87 后在 79 的槽里按 `align` 摆放（这里顶对齐），多出的 8 自然画到父容器外面——`Box` 默认不裁切，和 `ZStack` 行为一致。宽度同理用 `wrapContentWidth(unbounded = true)`。

排查提示：从 SwiftUI / 设计稿移植时，凡是「子元素位置 + 尺寸 > 父尺寸」的地方都要这么处理；症状不是报错，而是文字行数变少、图片被压扁。

## 相关链接

- 修复提交：QiuXiangBa/xuejieai-app#258（`features/home/HomeCards.kt` 的 `HomeDailyCard`）
- `Modifier.wrapContentHeight(align, unbounded)` 文档：https://developer.android.com/reference/kotlin/androidx/compose/foundation/layout/package-summary#(androidx.compose.ui.Modifier).wrapContentHeight(androidx.compose.ui.Alignment.Vertical,kotlin.Boolean)
