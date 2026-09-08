---
title: "NavigationLink destination 视图的 init 随父视图每次 body 求值重复执行"
stack: swift
platform: [ios]
versions: [ios 16.0 deployment target, xcode 26.6]
tags: [swiftui, navigationlink, performance, main-thread, state, disk-io]
project: xuejieai
status: solved
date: 2026-09-08
---

## 现象

列表页用 `NavigationLink { DetailView(id: item.id) }` 跳转详情，`DetailView.init` 里调用 `store.load()` 读本地文件、解 JSON、解码图片，用来初始化 `@State`。

结果列表页任何一个 `@State` 变化（输入框打字、下拉刷新、Tab 切换）都会触发一轮主线程磁盘读取，页面明显卡顿。在 `DetailView.init` 里打断点，父视图每次 body 求值都会进一次，进详情页前就已经执行了几十次。

## 原因

`NavigationLink { destination }` 的 destination 闭包是非逃逸的，SwiftUI 在**父视图每次 body 求值时都会立刻调用它构造目标视图实例**，而不是等到真正跳转。这些实例除了首次建立视图身份的那个外全被丢弃，`State(initialValue:)` 也只在首次生效，其余的初始化工作全是白做。

`navigationDestination(isPresented:)` 在 iOS 16.0 到 16.3 上也有同样的急切求值行为，部署目标是 16.0 时不能靠它规避。

视图的 init 只应做 O(1) 的值拷贝，任何 I/O 都会被放大成 N 次。

## 解决方案

init 里最多读 UserDefaults 这种内存级的东西，磁盘加载移到 `onAppear`，用自建 `Task` 后台读、主线程赋值：

```swift
struct DetailView: View {
    let id: String
    @State private var record: Record?
    @State private var loaded = false

    var body: some View {
        content
            .onAppear {
                guard !loaded else { return }
                loaded = true
                Task.detached(priority: .userInitiated) {
                    let value = await Store.shared.load(id)   // 后台读文件、解码
                    await MainActor.run { record = value }
                }
            }
    }
}
```

两个细节：

- 不用 `.task {}`：它绑定视图生命周期，用户秒退时会在赋值前被取消，而 `loaded` 已经置位，再进来就永远不加载了。自建 `Task` 让加载跑完再赋值。
- 如果同一份数据会有多个视图实例写回文件，写操作走串行队列并按 id 合并，否则多个实例 last-writer-wins 互相覆盖。

## 相关链接

- https://developer.apple.com/documentation/swiftui/navigationlink
- https://developer.apple.com/documentation/swiftui/view/task(priority:_:)
