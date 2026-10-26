---
title: "Compose GenericShape 多段子路径绕向不一致：NonZero 填充下交叠区被挖空"
stack: "kotlin"
platform: [android]
versions: ["compose-bom 2025.06.00 (ui 1.8.2)", "kotlin 2.1.20", "agp 8.11.1"]
tags: [compose, path, genericshape, winding, nonzero, addroundrect, swiftui-port, shape]
project: "xuejieai"
status: solved
date: "2026-10-26"
---

## 现象

把 SwiftUI 里一个「圆角矩形 + 右下小尾巴」的 `Shape` 照抄成 Compose 的 `GenericShape`：先 `addRoundRect(...)` 画气泡体，再 `moveTo / lineTo / close` 画一个三角形尾巴，尾巴有两个顶点在气泡体内部（根部伸进去衔接）。

SwiftUI 上是一整块；Compose 上尾巴根部伸进气泡体的那一小块（约 16×6 dp）变成透明缺口，气泡是半透明白压在浅色背景上时很难肉眼察觉，Review 通过叉积推出来后放大截图才确认。

```kotlin
// 有问题的写法（从 iOS Path 逐行翻译）
private val SpeechBubbleShape: Shape = GenericShape { size, _ ->
    val bodyHeight = size.height * 54.5f / 61f
    addRoundRect(RoundRect(Rect(0f, 0f, size.width, bodyHeight), CornerRadius(bodyHeight / 2)))
    val k = size.height / 61f
    val tailX = size.width * 0.91f
    moveTo(tailX - 8 * k, bodyHeight - 6 * k)   // 在气泡体内
    lineTo(tailX + 3 * k, size.height)          // 尾巴尖
    lineTo(tailX - 22 * k, bodyHeight - 1 * k)  // 在气泡体内
    close()
}
```

## 原因

`GenericShape` 的 `Path` 默认 `PathFillType.NonZero`：一个点被填充当且仅当各子路径绕它的绕数之和非零。

- Compose `Path.addRoundRect(roundRect, direction = Path.Direction.CounterClockwise)` **默认逆时针**（`AndroidPath.android.kt`）。
- 尾巴三点 A → B → C 在 y 向下的屏幕坐标里叉积为正，是**顺时针**。
- 两段子路径绕向相反，交叠区（尾巴根部伸进气泡体的部分）绕数 +1 + (−1) = 0，不填充。

iOS 同一组坐标没问题，是因为 Core Graphics 的 `addRoundedRect` 在 SwiftUI 翻转坐标系里恰好是顺时针，与尾巴同向。从 SwiftUI / CoreGraphics 逐行翻译 Path 时，绕向这个隐含约定不会跟着过来。

## 解决方案

让所有子路径绕向一致，二选一：

1. 给气泡体显式传方向（推荐，意图最清楚）：

   ```kotlin
   addRoundRect(RoundRect(Rect(0f, 0f, size.width, bodyHeight), CornerRadius(r)), Path.Direction.Clockwise)
   ```

2. 把尾巴顶点顺序反过来（A → C → B），改成逆时针与默认一致。

判断绕向：取三点 P0、P1、P2，算 `(x1−x0)(y2−y0) − (y1−y0)(x2−x0)`，在 y 向下坐标里 > 0 是顺时针。`addRect` / `addOval` / `addRoundRect` 都有 `direction` 参数，混合手画线段时一律显式写。另一条路是 `fillType = PathFillType.EvenOdd`？不行——EvenOdd 下交叠区同样不填，只有「绕向一致 + NonZero」才是并集。

验证：半透明形状压在浅色背景上缺口几乎看不出来，用 `adb exec-out screencap` 截图后把尾巴根部区域裁出来放大 8 倍看。

## 相关链接

- 修复提交：QiuXiangBa/xuejieai-app#258（`features/home/HomeScreen.kt` 的 `SpeechBubbleShape`）
- `androidx.compose.ui.graphics.Path.addRoundRect(roundRect, direction)` 文档：https://developer.android.com/reference/kotlin/androidx/compose/ui/graphics/Path#addRoundRect(androidx.compose.ui.geometry.RoundRect,androidx.compose.ui.graphics.Path.Direction)
