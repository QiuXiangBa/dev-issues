---
title: "SwiftUI 静止按压响应慢：从原始触摸时间戳定位手势延迟"
stack: swift
platform: [ios]
versions: ["iOS 27.0.1", "Xcode 27.2"]
tags: [swiftui, uikit, drag-gesture, touch-latency, xcuitest]
project: ios-client
status: solved
date: 2026-11-24
---

## 现象

一个按住即显示面板、松手提交、上滑取消的圆形按钮使用了 `DragGesture(minimumDistance: 0)`。手指按下并保持静止时，面板约四分之三秒后才出现。若从业务层的按压回调开始计时，到面板刷新只需几十毫秒，解释不了用户感受到的等待。

## 原因

在这台 iPhone 11 Pro 上，应用在触摸开始后约 6 毫秒就收到了 UIKit 事件。当手指保持静止时，SwiftUI 拖动手势的第一次 `onChanged` 却在约 759 毫秒才触发。一次较早上滑的对照中，手指按下约 300 毫秒后开始上滑，按下约 362 毫秒时就收到了回调。`minimumDistance: 0` 配置的是移动距离；在这个页面上，静止按住时首次回调仍会等待。759 毫秒是这组实测值。

## 解决方案

1. **从触摸开始计时。** 在诊断构建的 `UIApplication.sendEvent(_:)` 入口、分发事件前，记录按钮命中区域内主触点的 `.began` 和 `UITouch.timestamp`。同时记录到达应用的单调时钟时间。用同一时刻的 `CACurrentMediaTime() - ProcessInfo.processInfo.systemUptime` 估算两个时钟的偏移，将触摸时间转换到后续计时使用的时间轴。
2. **给同一次按压记录中间点。** 分别记录首次手势回调、业务开始处理、面板挂入窗口，以及挂窗后第一次 `CADisplayLink` 回调。最后一项用来近似面板首次刷新机会。保留触点的移动和结束事件，可区分静止长按与移动触发，也能发现以业务回调为起点时漏掉的时间。
3. **让需要即时反馈的按钮直接处理触摸开始。** 在原有 SwiftUI 按钮上用 `UIViewRepresentable` 加一层与圆形按钮等大的透明触控视图。局部自定义 `UIGestureRecognizer` 在 `touchesBegan` 中执行原有权限检查并开始业务动作，持续跟踪同一个触点，用窗口坐标计算上滑距离。在 `touchesEnded` 时提交或取消，系统中断或视图移除时取消。手指仍按住时保留触控视图，确保松手事件能送达。

**真机验证。** 在同一设备、同一按钮位置，用 XCUITest 向系统注入触摸。每种实现各测四次，其中一次静止按住 5 秒后松手，三次先静止 1.8 秒再上滑取消。下表为从系统记录的触摸开始算起的中位数。

| 观测点 | SwiftUI 拖动手势 | UIKit 首次触摸处理 |
|---|---:|---:|
| 应用收到触摸事件 | 6.4 毫秒 | 9.8 毫秒 |
| 业务按压回调 | 759.0 毫秒 | 10.1 毫秒 |
| 面板挂窗后首次刷新机会 | 783.5 毫秒 | 26.2 毫秒 |

单看静止 5 秒的那次，触摸到面板首次刷新机会由 792 毫秒降至 27 毫秒。新实现同时通过松手提交、上滑取消后重按，以及按住期间弹错后首次重试。此测量覆盖系统为触摸打上时间戳到显示刷新回调的链路；测量手指接触玻璃到屏幕像素变化的完整耗时需要外部观测。

## 相关链接

Apple 文档提供触摸时间戳的基准、拖动手势的距离参数和显示刷新回调的语义。[UITouch.timestamp](https://developer.apple.com/documentation/uikit/uitouch/timestamp) · [DragGesture](https://developer.apple.com/documentation/swiftui/draggesture) · [CADisplayLink](https://developer.apple.com/documentation/quartzcore/cadisplaylink)
