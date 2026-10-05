---
title: "Compose 照抄 SwiftUI 文字框左上角坐标，字会偏下：按首行基线对齐"
stack: "kotlin"
platform: [android, ios]
versions: ["compose-bom 2025.06.00", "kotlin 2.1.20", "ios 18 / 26"]
tags: [compose, swiftui, text, baseline, line-height, port, fixed-canvas, typography]
project: "tutuai"
status: solved
date: "2026-10-05"
---

## 现象

iOS（SwiftUI）和安卓（Compose）用同一份设计坐标做固定画布页面。安卓照抄 iOS 代码里 `Text(...).offset(x:y:)` 的左上角坐标，同字号的文字在安卓上明显偏下：中文最明显，35 号字偏下约 3 个设计单位，约 0.1 倍字号。坐标、尺寸、颜色都对，只有文字跑位。

在框内居中的文字（按框居中摆放）基本不受影响，偏差不到 1 个单位。

## 原因

两端「文字框」的高度和基线位置的算法不同：

- **SwiftUI**：文字框高度按系统字体的度量算。系统字体（含 `.rounded`）首行基线固定在框顶下方 **0.967 × 字号**（`NSFont.ascender / pointSize`），行高 **1.178 × 字号**，再向上取整到像素（35 号是 41.5）。纯中文也用这个框：苹方的度量更小，撑不高它。
- **Compose**：文字框高度跟着实际用到的字体走。中文回落到系统 CJK 字体，它的上升高度比拉丁字体大，框更高，基线更靠下。各厂商的系统字体也不一样，偏移量随设备变。

所以照抄左上角，对齐的是「框顶」，「基线」没有对齐。

另外，同字号下安卓系统字体的中文字形比 iOS 的苹方大约 9%，数字和英文基本一样大。这是字体本身的差别，不是排版问题。

## 解决方案

写一个布局修饰符，按**首行基线**而不是框顶摆放：基线放在 `y + 0.967 × fontSize`，不依赖设备字体的行高。

```kotlin
private const val IosFirstBaselineRatio = 0.967f

/** [x]、[y] 是 iOS 代码里这段文字的文字框左上角；[fontSize] 必须与文字样式里的字号一致（sp）。用在左上对齐的容器里。 */
fun Modifier.placeText(x: Dp, y: Dp, fontSize: TextUnit): Modifier = layout { measurable, constraints ->
    val placeable = measurable.measure(constraints.copy(minWidth = 0, minHeight = 0))
    val firstBaseline = placeable[FirstBaseline]
    val left = x.roundToPx()
    val top = if (firstBaseline == AlignmentLine.Unspecified) {
        y.roundToPx()
    } else {
        (y.toPx() + fontSize.toPx() * IosFirstBaselineRatio).roundToInt() - firstBaseline
    }
    // 上报尺寸夹在父约束内，否则框架会把超出的内容相对父约束居中
    layout(constraints.constrainWidth(placeable.width), constraints.constrainHeight(placeable.height)) {
        placeable.place(left, top)
    }
}

Text("专属", Modifier.placeText(26.dp, 148.dp, 35.sp), style = TextStyle(fontSize = 35.sp))
```

- iOS 那边是 `VStack(spacing: s)` 的多行文字时，安卓拆成逐行摆：下一行框顶 = 上一行框顶 + iOS 行高（1.178 × 字号，向上取到像素）+ 行距 `s`。
- 在框内居中的文字不用它，照旧居中摆放。
- 字形大小差约 9% 的问题这个方法不处理；要完全一致，只能两端打包同一款字体。

## 怎么量出来的（换平台、换字体时照此复核）

1. 在 macOS 上用 CoreText 取系统圆体的度量：`CTLineGetTypographicBounds` 得到 ascent / descent，`NSFont.ascender / pointSize` 得到 0.967。
2. iOS 模拟器和安卓模拟器各截同一页，按画布缩放（`min(屏宽/画布宽, 屏高/画布高)`，居中偏移）换算回设计坐标，量白字像素的包围盒，对比字形上下缘。改完后两端字形下缘相差 0–1.1 个单位（剩下的差来自两端字形本身）。

## 相关链接

- Compose `FirstBaseline` 对齐线：https://developer.android.com/reference/kotlin/androidx/compose/ui/layout/package-summary#FirstBaseline()
