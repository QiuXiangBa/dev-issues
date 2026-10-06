---
title: "Compose AnimatedContent 不向外转发子项的文字基线：旁边 alignByBaseline 的单位在内容更新后跳到数字顶边"
stack: "kotlin"
platform: [android]
versions: ["compose-bom 2025.06.00", "compose-animation 1.8.2", "kotlin 2.1.20"]
tags: [compose, animatedcontent, baseline, alignbybaseline, alignment-line, firstbaseline, text, animation]
project: "tutuai"
status: solved
date: "2026-10-06"
---

## 现象

「数字 + 单位」一行，数字要做滚动动画，所以包在 `AnimatedContent` 里，单位是普通 `Text`，两者在 `Row` 里用 `alignByBaseline()` 按基线对齐：

```kotlin
Row {
    AnimatedContent(targetState = value, modifier = Modifier.alignByBaseline()) { Text(it, style = big) }
    Text("m", Modifier.alignByBaseline(), style = small)
}
```

- 首次显示时对齐正常（单位贴着数字基线）。
- 数据刷新、`AnimatedContent` 的内容更新过一次之后（哪怕数值没变、没有播放过渡），单位跳到数字右上角：单位的基线对到了数字的**顶边**。外层 `Row` 若是垂直居中，整行还会跟着往下挪一点。
- 不报错，静态看代码也看不出来，只有在真机 / 模拟器上切换数据后才出现。

## 原因

`AnimatedContent` 的测量策略（`AnimatedContentMeasurePolicy`）不提供对齐线，内容更新后它不再把子项 `Text` 的 `FirstBaseline` 向上报。`Row` 读不到这一项的基线时，按基线位置 0（即顶边）处理，所以单位的基线对齐到数字顶边。（首次显示时为什么还是对的没有深究，可能是首次布局时对齐线还从子项继承到了；不要依赖这一点。）

就算能从子项继承基线，过渡期间新旧两份内容都在、各自带着滑动位移，读到的基线也会跟着动，单位会在动画中上下跳。

## 解决方案

不依赖 `AnimatedContent` 转发，在它外层自己报一个固定的首行基线：用同一个字样式量出文字的基线（同一样式各内容同高，静止时与真实基线重合，滚动途中单位也不动）。

```kotlin
@Composable
fun RollingText(text: String, style: TextStyle, modifier: Modifier = Modifier) {
    val measurer = rememberTextMeasurer()
    val baseline = remember(measurer, style) { measurer.measure("0", style).firstBaseline.roundToInt() }
    AnimatedContent(
        targetState = text,
        // 调用方传进来的 alignByBaseline() 等在 modifier 里，读的是下面这层报的基线
        modifier = modifier.layout { measurable, constraints ->
            val placeable = measurable.measure(constraints)
            layout(placeable.width, placeable.height, mapOf(FirstBaseline to baseline)) { placeable.place(0, 0) }
        },
        contentAlignment = Alignment.Center,
    ) { Text(it, style = style) }
}
```

注意：

- 量基线用的样式要和内容里 `Text` 实际生效的样式一致。Material3 `Text` 会合并 `LocalTextStyle`，如果外层套了 `MaterialTheme`（默认带 lineHeight 等），要用 `LocalTextStyle.current.merge(style)` 去量，或者内容里改用 `BasicText(style = style)`。
- 内容的高度要一致（同一字样式、单行），`contentAlignment` 居中；内容高度会变的场景这个固定值不成立。
- 顺带：`AnimatedContent` 的 `SizeTransform` 默认尺寸动画是 spring，宽度变化（位数变了、旁边的单位跟着横移）会比内容的 tween 过渡晚停；要同一节奏得显式传 `SizeTransform { _, _ -> tween(...) }`。

验证：数据切换前后各截一张图，放大看单位底边和数字底边是否在同一条线上；动画放慢（`adb shell settings put global animator_duration_scale 10`）录屏看过渡途中单位是否跟着跳。

## 相关链接

- Compose 源码 `androidx/compose/animation/AnimatedContent.kt`（`AnimatedContentMeasurePolicy`）
- 同库相关记录：`kotlin/2026-10-05-compose-text-baseline-match-swiftui.md`（照抄 SwiftUI 文字坐标时按基线对齐）
