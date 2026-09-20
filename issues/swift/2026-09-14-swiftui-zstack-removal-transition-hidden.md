---
title: "SwiftUI ZStack 里 if + transition 的自绘弹层关闭时瞬间消失（移除时掉层被盖住），需要 zIndex"
stack: "swift"
platform: [ios]
versions: [ios 16.0 deployment target, ios 18.6 simulator, xcode 26.6, xcode 27]
tags: [swiftui, zstack, transition, zindex, animation, bottom-sheet, overlay]
project: "xuejieai"
status: solved
date: "2026-09-14"
---

## 现象

页面 ZStack 里自绘一个底部弹出面板：

```swift
ZStack(alignment: .top) {
    PageContent()                       // 不透明整页
    if showsSheet {
        Color.black.opacity(0.68)
            .ignoresSafeArea()
            .onTapGesture { withAnimation { showsSheet = false } }
            .transition(.opacity)
        SheetPanel(onClose: { withAnimation(.easeInOut(duration: 0.25)) { showsSheet = false } })
            .transition(.move(edge: .bottom))
    }
}
```

打开有正常的滑入动画，但点 × / 点遮罩关闭时面板**一帧内消失**，没有任何滑出过程。用户反馈是"关闭不像系统 sheet、不丝滑"，很容易误判成动画曲线问题去调 spring 参数，其实根本没有出场动画。

用 `xcrun simctl io <udid> recordVideo` 录屏再逐帧抽帧对比才确认：打开跨 6～8 帧渐变，关闭只有 1 帧跳变。

## 原因

SwiftUI 的 ZStack 中，被 `if` 条件移除、带 `transition` 的视图在出场动画期间**会失去声明顺序赋予的层级，掉到其它兄弟视图下面**（除非显式给了 `zIndex`）。不透明的页面内容把整个滑出过程盖住，视觉上就是瞬间消失。

插入时不受影响（新视图正常排在上面），所以症状总是"开有动画、关没有"这种不对称。改 `withAnimation` 的曲线、时长都没用。

## 解决方案

**最小修法**：给遮罩和面板都加 `.zIndex(1)`（同值时仍按声明顺序叠放），出场动画立刻恢复：

```swift
if showsSheet {
    Color.black.opacity(0.68)
        .ignoresSafeArea()
        .onTapGesture { withAnimation { showsSheet = false } }
        .transition(.opacity)
        .zIndex(1)
    SheetPanel(onClose: { withAnimation { showsSheet = false } })
        .transition(.move(edge: .bottom))
        .zIndex(1)
}
```

注意同一 ZStack 里原本靠"声明在最后"压在最顶的其它弹层（如成功弹窗）也要相应给更高的 zIndex，否则层级语义被打破。

**结构性修法**（推荐新代码用）：不走 `if` + transition，把弹层做成挂在页面根上的 `.overlay`，遮罩用 `opacity`、面板用 `offset(y:)` 驱动，视图常驻、只改状态。这样没有插入 / 移除，也就没有掉层问题，还能顺手接上拖拽跟手关闭：

```swift
extension View {
    func bottomSheet<Content: View>(isPresented: Binding<Bool>, @ViewBuilder content: @escaping () -> Content) -> some View {
        overlay { BottomSheetOverlay(isPresented: isPresented, content: content).ignoresSafeArea() }
    }
}

private struct BottomSheetOverlay<Content: View>: View {
    @Binding var isPresented: Bool
    let content: () -> Content
    @State private var isShown: Bool          // 视觉状态，跟 isPresented 走，拖拽关闭时可用松手速度出场
    @State private var dragOffset: CGFloat = 0

    var body: some View {
        GeometryReader { proxy in
            let sheetHeight = proxy.size.height - topInset
            ZStack(alignment: .bottom) {
                Color.black.opacity(0.68)
                    .opacity(isShown ? 1 : 0)
                    .contentShape(Rectangle())
                    .onTapGesture { isPresented = false }
                content()
                    .frame(height: sheetHeight)
                    .offset(y: isShown ? dragOffset : sheetHeight)
                    .gesture(DragGesture(minimumDistance: 8)
                        .onChanged { dragOffset = max(0, $0.translation.height) }
                        .onEnded { value in
                            let projected = max(value.translation.height, value.predictedEndTranslation.height)
                            if projected > 96 { isPresented = false }
                            else { withAnimation(.spring(response: 0.5, dampingFraction: 1)) { dragOffset = 0 } }
                        })
            }
            .allowsHitTesting(isPresented)
            .onChange(of: isPresented) { shown in
                withAnimation(.spring(response: 0.5, dampingFraction: 1)) { isShown = shown; dragOffset = 0 }
            }
        }
    }
}
```

要点：

- 面板常驻视图树，内容里按"打开时机"拉数据的用 `.task(id: isPresented)`，语义等同于原来挂在条件视图上的 `.task`（关闭取消、再开重跑）。
- 拖拽手势用 `.gesture` 挂整块面板：被 ScrollView / 控件接管的区域不会触发，固定高面板实际只有头部可拖；用 `simultaneousGesture` 会和内部滚动同时动。
- `spring(response: 0.5, dampingFraction: 1)` 是接近系统 sheet 的临界阻尼曲线，不回弹。

**排查建议**：遇到"关闭不丝滑"先录屏抽帧（`recordVideo` + `AVAssetImageGenerator` 逐帧存 PNG），分清是曲线问题还是根本没动画，再动手。

## 相关链接

- https://developer.apple.com/documentation/swiftui/view/zindex(_:)
- https://developer.apple.com/documentation/swiftui/view/transition(_:)

## 更新 2026-09-15

同一个坑的第二种症状：**关闭时弹层"掉到某个兄弟下面"，而不是整个瞬间消失**。

同一页 ZStack 里已经有一个兄弟显式给了 `.zIndex(1)`（本例是日历头，为了让把手热区溢出到兄弟之上），顶栏下拉的自绘弹层（`if` + `.transition(.scale.combined(with: .opacity))`）没给 zIndex。打开正常；关闭那一帧弹层掉层，但页面主体没有 zIndex、仍在弹层之下，所以只有带 `zIndex(1)` 的日历头压到弹层上面——录屏抽帧看到弹层淡出过程中被周条盖住上半截，用户描述是"图层发生变化、直接到下面去了"。

判断规则：**只要 ZStack 里有任何兄弟显式给了 zIndex，`if` 弹层的移除层级问题一定会以某种形式露出来**（被谁盖住取决于谁有 zIndex）。修法不变：遮罩和弹层都给一个比那个兄弟更高的 `.zIndex`（本例 `.zIndex(2)`）。新写弹层时直接给 zIndex，不要等症状出现。

## 更新 2026-09-20

同一个坑的第三种症状：**不是 `if`，而是 `.id(pageID)` 换内容 + 横滑 transition，滑出的旧页只被挡住一部分**。

分页内容写成 `page(current).id(current.id).transition(.move…)`，夹在 ZStack 的背景装饰层和顶部 chrome 之间，都没给 zIndex。换页时滑入的新页正常，滑出的旧页掉到最底：背景装饰层里不透明的那一条（本例是一条横贯的平台色带）把旧页的下半截盖住，其余透明区域旧页照常可见——所以看起来不是「消失」，而是「滑出途中卡片下半截突然被切掉」。录屏逐帧才看得出来，肉眼只觉得换页时闪了一下。

结论：`.id` 变化导致的移除和 `if` 移除走的是同一套机制，同样掉层。修法不变：参与 transition 的内容给 `.zIndex(1)`，原本靠声明顺序压在它上面的兄弟（chrome）给 `.zIndex(2)`；背景和其它分支（loading / 空态）保持默认 0 即可，叠放顺序与改动前一致。

versions 补充：xcode 27。带方向的横滑写法见 `issues/swift/2026-09-20-swiftui-directional-transition-outside-id.md`。
