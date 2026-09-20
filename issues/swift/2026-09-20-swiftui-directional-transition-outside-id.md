---
title: "SwiftUI 方向可变的横滑换页 transition：.transition 挂在 .id 外层，方向状态与 id 同一次更新即可正确翻转"
stack: "swift"
platform: [ios]
versions: [ios 16.0 deployment target, ios 18.6 simulator, xcode 27]
tags: [swiftui, transition, asymmetric, move-edge, id, identity, animation, paging, direction]
project: "tutuai"
status: solved
date: "2026-09-20"
---

## 现象

分页类内容（按周 / 按月 / 按章节）换页要做带方向的横滑：往后翻时旧页左出、新页右进，往回翻时反过来。常见写法是 `.asymmetric(insertion: .move(edge:), removal: .move(edge:))`，两条边按一个方向状态取值。

这类写法有个广为流传的坑：**方向翻转的那一次，被移除的旧页沿用上一次的方向**（「慢一拍」）——比如一直往后翻，第一次往回翻时新页从左进是对的，旧页却仍然向左出，两页叠在同一侧。常见的兜底是「先设方向，`DispatchQueue.main.async` 再 `withAnimation` 换页」，多一次 runloop、代码也绕。

## 原因

被移除视图用哪个 transition，取决于 `.transition` 修饰符挂在视图树的什么位置：

- `.transition` 挂在 `.id(pageID)` **外层**：换页只是换掉 id 子节点，新旧两页共用同一个 transition 修饰符。方向状态和 id 在同一次更新里变，更新后新旧两边读到的都是新方向。
- `.transition` 挂在 `.id` **里面**，或者两页写成 `if / else` 两个分支各带各的 transition：被移除的那一页已经不在新的 body 里，只能用它上一次渲染时的值，方向就慢一拍。（这一条是读代码的推断，本次没有构造反例实测；「慢一拍」现象本身是社区里常见的报告。）

注意：`slidesForward = …` 紧跟着 `withAnimation { 换页 }` 写在同一个同步函数里，两次状态变更会合并进同一次 body 求值，**并不存在「方向先落一次渲染」**。方向正确靠的是上面的挂载位置，不是赋值顺序。

## 解决方案

```swift
@State private var slidesForward = true

var body: some View {
    ZStack {
        background
        page(current).id(current.id)
            .transition(pageTransition)   // 挂在 .id 外层
            .zIndex(1)                    // 见相关链接：被移除视图会掉层
        chrome.zIndex(2)
    }
}

private var pageTransition: AnyTransition {
    .asymmetric(insertion: .move(edge: slidesForward ? .trailing : .leading),
                removal: .move(edge: slidesForward ? .leading : .trailing))
        .combined(with: .opacity)
}

private func select(_ target: Page) {
    guard let from = pages.firstIndex(where: { $0.id == current.id }),
          let to = pages.firstIndex(where: { $0.id == target.id }),
          from != to else { return }          // 重选当前页不播空动画
    slidesForward = to > from
    withAnimation(.easeInOut(duration: 0.35)) { current = target }
}
```

要点：

- 所有换页入口（「下一页」按钮、页码菜单）都走同一个 `select`，方向按下标比较，不要各入口各写一份。
- 叠 `.opacity`：`.move(edge:)` 只位移视图自身宽度，屏幕比内容宽（等比缩放画布的留边）时旧页滑到头仍有一截露在留边里，淡到透明后再移除就不会「啪」地消失。
- 新页 `onAppear` 里需要 `scrollTo` 定位的，放进 `DispatchQueue.main.async`：出了动画事务就不会变成带动画的滚动，实测滑入首帧已经在目标位置，没有跳动。
- 已实测（iOS 18.6 模拟器，`simctl recordVideo` 逐帧抽图）：前进 → 往回方向翻转那一次，新旧两页方向都正确。**iOS 16 / 17 未验证**；若低版本上方向慢一拍，退回「先设方向、下一个 runloop 再 `withAnimation`」。
- 已知小瑕疵：过渡飞行途中再反向换页，正在滑出的那一页移除边可能中途改变（观感问题）；介意就在过渡期间给内容加 `allowsHitTesting(false)`。

## 相关链接

- 被移除视图在 ZStack 里掉层（同一场景必然同时遇到）：`issues/swift/2026-09-14-swiftui-zstack-removal-transition-hidden.md`
- https://developer.apple.com/documentation/swiftui/anytransition/asymmetric(insertion:removal:)
- https://developer.apple.com/documentation/swiftui/view/id(_:)
