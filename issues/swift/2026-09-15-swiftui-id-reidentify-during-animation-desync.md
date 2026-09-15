---
title: "SwiftUI 动画中途用 .id 重建子视图会和父容器动画脱节（常驻底部弹窗快速重开时白底先到、内容慢半拍）"
stack: "swift"
platform: [ios]
versions: [ios 16.0 deployment target, ios 18.6 simulator, xcode 26.6]
tags: [swiftui, id, identity, animation, offset, bottom-sheet, state-reset]
project: "xuejieai"
status: solved
date: "2026-09-15"
---

## 现象

自定义底部弹窗组件：面板（白底 + 内容）常驻视图树，用 `offset(y:)` 在 0 和"整块出屏"之间做开合动画（弹簧约 0.5s）。面板内容带表单草稿（`@State`），为了每次打开都重置草稿，宿主用"打开计数"给内容视图挂 `.id`：

```swift
Button("打开") {
    openCount += 1          // 让内容视图重建，草稿归零
    isPresented = true
}
…
.bottomSheet(isPresented: $isPresented) {
    SheetContent(...)
        .id(openCount)
}
```

第一次打开完全正常。**关闭后间隔很短（关闭动画还没走完）再点打开**，面板白底先滑到位，标题 / 表单内容慢半拍才追上来，肉眼看是"背景和内容不一致"。间隔长一点再开又正常，所以常规走查抓不到，用户手快才会碰到。

用 `xcrun simctl io <udid> recordVideo` 录屏、按 60fps 抽帧对比：同一帧里白底顶边已在最终位置，内容还在下方十几到几十 pt 处继续上移，两者用的是不同的动画曲线。

## 原因

`.id` 变化等于把旧视图移除、插入一个全新视图。此时父容器（面板）的 `offset` 动画还在飞：

- 旧的动画事务只作用于面板本身（白底属于面板的 `background`），偏移反向回 0 沿用原来的曲线继续；
- 新插入的内容视图没有参与那个事务，SwiftUI 按它被插入时的位置另起一个位置动画，起点、曲线都和面板不同。

于是面板底和内容各走各的，直到两边都停下才重合。只要视图身份在**父容器动画进行中**被换掉，就会出现这种脱节；不局限于底部弹窗，任何 `offset` / `position` / `matchedGeometry` 动画中的容器换子视图身份都可能触发。

## 解决方案

不换视图身份，让内容视图自己在打开时重置状态：

```swift
struct SheetContent: View {
    @Binding var isPresented: Bool
    @State private var draft: Draft

    var body: some View {
        form
            .onChange(of: isPresented) { if $0 { resetDraft() } }   // 打开时重置，身份不变
            .task(id: isPresented) { if isPresented { await reload() } }
    }

    private func resetDraft() {
        draft = Draft(from: source)   // 编辑副本 / 已保存基线 / 输入框 / 弹窗状态一并归零
    }
}
```

宿主去掉 `openCount` 和 `.id`，打开只置 `isPresented = true`。修完再按同样方式录屏抽帧：关闭动画走到一半反向重开，白底与内容逐帧同步。

要点：

- 常驻（不销毁）的面板内容，重置状态用 `onChange(of: isPresented)`，别用 `.id` 重建。
- `.id` 重建只在视图**不在动画中**时安全；凡是能被快速连点的入口都不满足这个前提。
- 验证时必须做"关闭后立刻再开"这一档，普通的"开 → 等 → 关 → 等 → 开"走查发现不了。

## 相关链接

- 同一组件的另一个坑（`if` + `transition` 自绘弹层关闭时掉层）：`issues/swift/2026-09-14-swiftui-zstack-removal-transition-hidden.md`

## 更新 2026-09-15

把同一修法推广到另外两个面板时踩到 `onChange` 的一个配套坑：用 `.onChange(of: isPresented) { if $0 { resetDraft() } }` 重置，`resetDraft()` 里直接读 `self.editing`（宿主传进来的普通 `let`），结果编辑面板打开时表单是空的、随后的新建面板反而预填了上一条——草稿永远慢一拍。

原因：`onChange(of:perform:)` 触发时跑的是**上一轮 body 注册的闭包**，闭包捕获的 `self` 是旧的视图值。宿主在同一事务里先改编辑目标再置 `isPresented = true`，闭包看到的 `editing` 仍是上次打开的。第一处面板没踩到，只因为它重置时读的是 `@Binding`（走的是 State 存储，永远最新）。

解法二选一：

- 需要的值从 Binding 读；
- 或者把需要的值塞进被观察的值里，从闭包参数取（闭包参数是新值）：

```swift
private struct DraftSource: Equatable { let editing: Item?; let day: Date }

.onChange(of: isPresented ? DraftSource(editing: editing, day: day) : nil) { source in
    if let source { resetDraft(from: source) }     // 用 source.editing，不用 self.editing
}
```

验证要走「编辑 A → 关 → 新建 → 关 → 编辑 B」这条切换链，只看"快速重开动画"抓不到。
