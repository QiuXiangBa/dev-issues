---
title: "Compose ModalBottomSheet 是独立窗口，会盖住 Activity 窗口内的叠层页面"
stack: "kotlin"
platform: [android]
versions: ["compose-bom 2025.06.00", "material3 1.3.x", "kotlin 2.1.20"]
tags: [compose, material3, modal-bottom-sheet, window, z-order, overlay, ime]
project: "kakaai"
status: solved
date: "2026-09-18"
---

## 现象

页面用 M3 `ModalBottomSheet` 做半屏确认弹窗，弹窗里有个可点的链接，点了要打开一个「全屏详情页」。这个详情页不是路由页，而是 Activity 内容树里的窗口内叠层：

```kotlin
Box(Modifier.fillMaxSize()) {
    Content()
    AnimatedVisibility(visible = detailVisible, enter = slideInVertically { it }) {
        DetailScreen(onClose = { detailVisible = false })
    }
}
```

在弹窗里把 `detailVisible` 置 true 后，详情页确实滑出来了，但**出现在弹窗下面**，被遮罩和弹窗盖住，看不见也点不到。没有报错，给详情页加 `zIndex` 也无效。

## 原因

M3 `ModalBottomSheet` 不在 Activity 的组合树里绘制，而是开一个**独立 window**（Dialog 形态）。窗口间的 z 序由 WindowManager 决定，独立窗口永远高于 Activity 窗口内的任何 composable，`Modifier.zIndex` 只在同一窗口的同级节点间生效，管不到这里。`Dialog` / `Popup` / `AlertDialog` 同理。

对比：SwiftUI 的 `.sheet` 里可以直接再嵌一个 `.sheet` 往上叠，没有这个问题。

## 解决方案

点击时**先播收起动画，再触发打开**，调用方同时把控制弹窗显隐的 state 置 false：

```kotlin
val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
val scope = rememberCoroutineScope()
// 按钮 / 链接触发的关闭：先收起再回调（遮罩点击 / 返回键由 M3 内部先动画再回调 onDismissRequest）。
fun hideThen(action: () -> Unit) {
    scope.launch { sheetState.hide() }.invokeOnCompletion { if (!sheetState.isVisible) action() }
}

ModalBottomSheet(onDismissRequest = onDismiss, sheetState = sheetState) {
    Text("查看详情", Modifier.clickable { hideThen { onOpenDetail() } })
}

// 调用方
if (showSheet) {
    ConfirmSheet(
        onDismiss = { showSheet = false },
        onOpenDetail = { showSheet = false; detailVisible = true },
    )
}
```

连点安全：第二次 `hide()` 会经 mutator 取消第一次，第一次的 `invokeOnCompletion` 触发时 `isVisible` 仍为 true 所以不回调，**只有最后一次点击生效**，不会重复触发动作。

备选方案：把目标页也放进独立窗口（`Dialog(properties = DialogProperties(usePlatformDefaultWidth = false))` 或另一个 sheet），或改成导航路由页。

附带两条同场景经验：

- **弹 sheet 前先收键盘**：`LocalFocusManager.current.clearFocus()`。若 sheet 的 `contentWindowInsets` 被置零（自己处理导航条 inset 时常这么写），个别机型 IME 不自动收起，会盖住 sheet 底部按钮。
- **iOS 侧对应坑**：sheet 关闭后要接着触发「会弹新页面 / 换根视图」的动作时，放到 `.sheet(isPresented:onDismiss:)` 的 `onDismiss` 里执行（用一个 pending 标记区分「确认关闭」和「取消关闭」）。在置 `isPresented = false` 的同一刻就执行，后续的 `fullScreenCover` 可能撞上收起动画，被 UIKit 以「正在 dismiss 时 present」静默丢弃。

## 相关链接

- ModalBottomSheet API：https://developer.android.com/reference/kotlin/androidx/compose/material3/package-summary#ModalBottomSheet
- SheetState.hide：https://developer.android.com/reference/kotlin/androidx/compose/material3/SheetState
