---
title: "Compose lint 的 ModifierDeclarationDetector 遇到返回 Modifier 的扩展函数 NoClassDefFoundError，整个 lint 任务失败"
stack: "kotlin"
platform: [android]
versions: ["agp 8.11.1 (lint 31.11.1)", "compose-bom 2025.06.00 (ui 1.8.x)", "kotlin 2.1.20", "gradle 8.14.3"]
tags: [lint, compose, modifier, agp, androidx, modifier-declaration-detector]
project: "xuejieai"
status: workaround
date: "2026-10-23"
---

## 现象

工程 `./gradlew lint` 一直是绿的。在一个 Compose 页面文件里加了一个返回 `Modifier` 的扩展函数：

```kotlin
private fun Modifier.verticalFade(opaqueUntil: Float, transparentFrom: Float = 1f): Modifier =
    graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }
        .drawWithContent { drawContent(); drawRect(brush = …, blendMode = BlendMode.DstIn) }
```

之后 lint 任务直接崩掉（不是报 lint 问题，是检查器本身异常）：

```
Execution failed for task ':app:lintAnalyzeDebug'.
> Unexpected failure during lint analysis of LoginScreen.kt (this is a bug in lint or one of the libraries it depends on)
  Message: androidx/compose/lint/Names$Ui$Layout
  The crash seems to involve the detector `androidx.compose.ui.lint.ModifierDeclarationDetector`.
  You can try disabling it with something like this:
      android { lint { disable "ModifierFactoryExtensionFunction", "ModifierFactoryReturnType", "ModifierFactoryUnreferencedReceiver" } }
  Stack: `NoClassDefFoundError:ModifierDeclarationDetector$createUastHandler$1.visitMethod(ModifierDeclarationDetector.kt:89)←…`
```

## 原因

compose-ui 发布包里捆绑的 lint 检查（`ui-lint`）引用了 `androidx.compose.lint:common` 的 `Names.Ui.Layout`，而当前 AGP 自带的 lint 运行时里这个类不可见（Compose 版本与 AGP/lint 版本组合不兼容）。`ModifierDeclarationDetector` 只在访问到「返回类型是 `Modifier` 的函数」时才走到那行代码，所以工程里一个 `fun Modifier.xxx(): Modifier` 都没有的时候不会触发，一加就崩。

## 解决方案

绕开（本项目采用）：**不在业务模块声明返回 `Modifier` 的函数**。可复用的绘制逻辑写成 `ContentDrawScope` / `DrawScope` 扩展，调用处直接串 `graphicsLayer` + `drawWithContent`：

```kotlin
private fun ContentDrawScope.drawWithVerticalFade(opaqueUntil: Float, transparentFrom: Float = 1f) {
    drawContent()
    drawRect(
        brush = Brush.verticalGradient(opaqueUntil to Color.Black, transparentFrom to Color.Transparent),
        blendMode = BlendMode.DstIn,
    )
}

Box(
    Modifier
        .graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }
        .drawWithContent { drawWithVerticalFade(opaqueUntil = 0.8f) },
)
```

或者按 lint 的提示关掉这三条检查（代价是失去对 Modifier 工厂函数的规范检查）：

```kotlin
android {
    lint {
        disable += listOf("ModifierFactoryExtensionFunction", "ModifierFactoryReturnType", "ModifierFactoryUnreferencedReceiver")
    }
}
```

根治应是把 AGP（lint）与 Compose 升到互相匹配的版本，未验证。

## 相关链接

- 暂无对应的 issuetracker 条目（未查到）
