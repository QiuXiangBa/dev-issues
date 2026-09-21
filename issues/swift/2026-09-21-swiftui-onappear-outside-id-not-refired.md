---
title: "SwiftUI .id(x).onAppear：只换 id 时挂在 .id 外层的 onAppear 不再触发"
stack: "swift"
platform: ["ios"]
versions: ["swiftui", "ios 16 deployment target", "ios 27 simulator", "xcode 27"]
tags: ["swiftui", "id", "identity", "onappear", "task", "side-effect", "prefetch", "cache-hit", "autoplay"]
project: "tutuai"
status: solved
date: "2026-09-21"
---

## 现象

做题页「进入每道题先自动朗读一遍」，写法是把副作用挂在 `.id` 之后：

```swift
QuestionBoard(item: item)
    .id(item.id)                       // 换题整块重建
    .onAppear { sound.play(item.audioURL) }
```

- 第 1 题会读；点「下一题」换题后**不读**，没有任何报错。
- 加了「预取下一题数据」之后才出现；没有预取时每题都读，看起来像偶发。

## 原因

`.onAppear` 挂在 `.id()` 的**外层**。

- 下一题数据未缓存时：状态 `.loading`（内容被移除）→ 等网络 → `.loaded(next)`（内容重新插入）。视图是真的新出现，外层 `onAppear` 触发。
- 下一题数据已预取（缓存命中）时：`.loading → .loaded(next)` 在同一次更新里完成，中间没有挂起点，SwiftUI 看不到「移除」这一帧。视图没被移除，只是 `.id` 的值变了。

`.id` 值变化只会让它**包住的内部视图**换身份、整块重建（内部 `@State` 归零，内部的 `.onAppear` / `.task` 重新触发）；挂在 `.id(...)` 之后的修饰符属于外层，身份没变，它的 `onAppear` 不会再触发。

## 解决方案

依赖 `.id` 重建来触发的副作用（自动播放、计时、重置、埋点）一律挂在**被重建的视图内部**：

```swift
struct QuestionBoard: View {
    let item: Item
    let sound: SoundPlayer

    var body: some View {
        content
            // 在 .id 里面：每次换题随本视图重建触发
            .onAppear { sound.play(item.audioURL) }
    }
}

QuestionBoard(item: item, sound: sound)
    .id(item.id)
```

注意和 transition 的规则正好相反：方向可变的 `.transition` 要挂在 `.id` **外层**（新旧视图共用同一个修饰符，方向才同步），而「每次重建都要跑一次」的副作用要挂在 `.id` **里面**。

排查 / 验证时踩的两个坑：

- 验证日志要打在真正承载副作用的那个闭包里。只验证了「内部 `.task` 每次重建都跑」，推不出「外层 `onAppear` 也会跑」。
- `xcrun simctl launch --console` 下 `print` 走管道是块缓冲，进程被 terminate 时末尾输出会丢，容易误判「没触发」；用 `NSLog`（走 stderr，不缓冲）才可靠。声音类行为自动化听不到，用临时自动点击脚本 + `NSLog` 验证触发点，听感再请人确认。

## 相关链接

- 同库相关记录：`issues/swift/2026-09-20-swiftui-directional-transition-outside-id.md`（transition 挂 `.id` 外层）
- Apple 文档：<https://developer.apple.com/documentation/swiftui/view/id(_:)>
