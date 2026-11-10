---
title: "SwiftUI 应用降低到 iOS 15 时要同时回退异步等待和页面效果"
stack: "swift"
platform: ["ios"]
versions: ["iPadOS 15.8.8", "Xcode 27.2", "Swift concurrency", "SwiftUI"]
tags: ["ios15", "back-deployment", "swiftui", "task-sleep", "cancellation", "availability"]
project: "ios-compatibility-example"
status: "solved"
date: "2026-11-10"
---

## 现象

把最低部署版本从 iOS 16 降到 15.8 后，等待、超时计算、播放心跳中的 `Task.sleep(for:)` 无法在旧系统使用；菜单、数字转场、自适应行布局等页面效果也依赖新 API。只调整 deployment target，不能完成兼容。

即使某条编译错误已消除，仍可能出现短菜单空拖动、弹层按钮不可操作、头像行溢出，或者旧系统效果与预期不一致。还要区分 API 不可用与 Foundation 等框架的运行时行为变化。

## 原因

- `Task.sleep(for:)` 的 Duration 版本与部分 SwiftUI API 要求 iOS 16；已有 `Task.sleep(nanoseconds:)` 可用于旧分支。
- 更高版本的布局/修饰符不可直接移植。把新 API 包进一个未受可用性保护的辅助函数，也不会自动获得回退实现。
- 版本检查要按具体重载核对。例如 `.numericText()` 与 `.numericText(value:)` 的最低版本并不相同，不能只搜索方法名。
- 用新系统模拟器通过编译和走查，只能覆盖实际运行过的版本分支。

## 解决方案

### 1. 集中等待逻辑，保留取消语义

业务调用统一传秒数，不在各处换算纳秒。下面接口约定输入是项目内部有限、短时的秒数；若接收外部或任意时长，应先验证非有限值及纳秒转换上界。

```swift
import Foundation

enum AsyncDelay {
    static func sleep(seconds: TimeInterval) async throws {
        try Task.checkCancellation()
        let interval = max(0, seconds)
        if #available(iOS 16.0, macOS 13.0, *) {
            try await Task.sleep(for: .seconds(interval))
        } else {
            try await Task.sleep(nanoseconds: UInt64(interval * 1_000_000_000))
        }
    }
}
```

先检查取消，保证已取消任务即使收到零或过期的超时时长也抛 `CancellationError`。调用处保留原有 `try`、错误处理和循环中的取消检查；不要顺手把等待改成不可取消的 Timer 或忙等。集中迁移时检查加载延迟、超时竞争、重试间隔、媒体心跳和页面退场任务，避免漏掉非 UI 调用。

### 2. 为页面效果定义明确的旧系统行为

| 功能 | 新系统路径 | iOS 15 回退 |
| --- | --- | --- |
| 短菜单是否允许滚动 | iOS 16+ `scrollDisabled` | 短列表直接展示内容，溢出时才创建 ScrollView |
| 文字/数字转场 | iOS 16+ `contentTransition`、无 value 参数的 `numericText()` | 仅在 Text 节点上用 `.id(value)` 与 opacity 交叉淡变 |
| 数字值专用转场 | `numericText(value:)` 要求 iOS 17+ | 按该重载的可用性单独分支 |
| 一行头像/按钮自适应 | iOS 16+ `ViewThatFits` | 已知固定槽位直接排一行，超过容量才横向滚动 |
| Home 指示条 | iOS 16+ View 的 `persistentSystemOverlays(.hidden)` | 保留系统默认，不劫持 SwiftUI 控制器生命周期 |
| 键盘滚动收起 | iOS 16+ 交互式收起 | 旧系统按页面需要用拖动结束编辑 |
| CGPath 差集阴影 | 使用受可用性保护的新路径运算 | 按几何关系用奇偶填充并只裁阴影层，独立绘制描边 |

共同辅助视图示例：

```swift
struct MenuScrollView<Content: View>: View {
    let isScrollEnabled: Bool
    @ViewBuilder let content: () -> Content

    var body: some View {
        if #available(iOS 16.0, *) {
            ScrollView(.vertical, showsIndicators: false, content: content)
                .scrollDisabled(!isScrollEnabled)
        } else if isScrollEnabled {
            ScrollView(.vertical, showsIndicators: false, content: content)
        } else {
            content()
        }
    }
}
```

转场回退读取 `accessibilityReduceMotion`，启用减弱动态效果时取消相应动效。只重建展示 Text，避免把整个表单、播放器或持有业务状态的父视图挂到变化的 `.id` 上。

### 3. 验证两种问题，分别保留证据

- 等待逻辑检查小数秒、零/负的剩余时长、等待中取消及进入前已取消。现代宿主运行此接口不会覆盖旧系统 sleep 分支，仍需旧系统运行或独立分支测试。
- 真机检查菜单展开/选择/关闭、溢出滚动、日期和提示切换、头像布局、通关描边，以及录音/播放心跳涉及的流程。
- 生产数据没有溢出列表、统计数字未变化或未开启减弱动态效果时，对应效果只能记未覆盖。
- 本方案在 iPadOS 15.8.8 真机执行过功能回归；不把一次回归当作所有低版本和长时性能的认证。
- 如果图片空白、素材被丢弃或音频被当作未配置，还要核对下面的资源 URL 解析问题，不能全部归因于 SwiftUI。

## 相关链接

- [Swift Task.sleep](https://developer.apple.com/documentation/swift/task/sleep(for:tolerance:clock:))
- [SwiftUI scrollDisabled](https://developer.apple.com/documentation/swiftui/view/scrolldisabled(_:))
- [SwiftUI ViewThatFits](https://developer.apple.com/documentation/swiftui/viewthatfits)
- [SwiftUI ContentTransition](https://developer.apple.com/documentation/swiftui/contenttransition)
- [旧系统中文资源 URL 编码](2026-11-10-ios15-unicode-resource-url-encoding.md)
