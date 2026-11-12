---
title: "SwiftUI 相机黑屏的全屏呈现修复与草稿生命周期保护"
stack: "swift"
platform: ["ios"]
versions: ["Swift 6.4", "Xcode 27.1", "iPhoneOS SDK 27.1", "iOS 27.0.1"]
tags: ["swiftui", "uikit", "camera", "fullscreen", "view-lifecycle", "draft-state"]
project: "<sample-project>"
status: workaround
date: "2026-11-12"
---

## 现象

SwiftUI 编辑页用 `UIViewControllerRepresentable` 包装 `UIImagePickerController`，通过 `.sheet` 打开相机。实际 iPhone 屏幕也无法取景，不能仅解释为电脑镜像不显示相机。

改为全屏相机还会暴露另一个生命周期问题：相机覆盖编辑页时，编辑页可能收到 `onDisappear`。若此时一律清理草稿、撤销照片上传或重置表单，用户取消拍照返回后可能丢失原输入或原照片。

## 原因

相机呈现方式与编辑页的离场判定需要分别处理：

- UIKit 的相机界面应按平台指导全屏呈现；SwiftUI 的外层容器也需要与之匹配。
- `onDisappear` 不等于用户取消了编辑。被自身的全屏相机覆盖和真正离开编辑流程，可以触发相同的外观回调。

本次调整后，原故障设备复测恢复正常，但没有隔离证明非全屏呈现是黑屏的唯一根因。因此将黑屏处理记录为已验证的 workaround，不推广为所有相机黑屏的通用诊断结论。

## 解决方案

### 同时调整两层呈现

SwiftUI 容器使用 `fullScreenCover`；包装的控制器明确设置 `modalPresentationStyle = .fullScreen`。打开前继续检查硬件能力与相机权限，不在没有相机的环境强行使用 `.camera`。

以下是流程示意，`CameraPicker`、草稿状态和清理方法由项目提供：

```swift
.fullScreenCover(isPresented: $showsCamera) {
    CameraPicker { capturedData in
        if let capturedData {
            photoData = capturedData
        } // 取消时不以 nil 覆盖原照片
        showsCamera = false
    }
    .ignoresSafeArea()
}
.onDisappear {
    guard !showsCamera else { return }
    abandonUnsavedDraft()
}
```

在 `makeUIViewController` 中配置相机控制器：

```swift
picker.sourceType = .camera
picker.modalPresentationStyle = .fullScreen
```

### 将草稿所有权与可见性分开

- 仅在本编辑页的相机覆盖期间跳过“真正退出”的草稿清理。
- 用户取消编辑、保存成功、账号重置仍保留各自的清理和隔离路径，不把所有 `onDisappear` 清理永久移除。
- 取消相机不覆盖已有照片；确认新照片后才替换。异步照片读取还应核对请求标识与账号作用域，拒绝旧结果。
- `onDisappear` 提前返回不会阻止 SwiftUI 管理的 `.task` 被取消；不要把保留表单值误当成后台读取任务一定继续。取消检查、异步结果发布与草稿清理需要独立设计。

### 验证范围

至少检查原故障设备本机取景、首次取消、重新拍摄、已有照片后再取消、字段保留、保存与照片绑定；后台再回前台作为单独场景。

本次证据为：新包在原设备复测获用户一般性“正常”回报，随后观察到保存记录及照片缩略图，并以一次只读样本确认照片正确绑定且存储字节非空。没有采集图片内容或表单文本。取消/重开及字段保留没有完整独立交互录像，后台恢复未明确实测。83项单测、编译和独立源码审查通过，不能替代相机预览及完整生命周期的实机验证。

## 相关链接

- [Apple：UIImagePickerController](https://developer.apple.com/documentation/uikit/uiimagepickercontroller)：相机的能力检查、呈现与取消流程。
- [Apple：fullScreenCover(isPresented:onDismiss:content:)](https://developer.apple.com/documentation/swiftui/view/fullscreencover(ispresented:ondismiss:content:))。
- [相关：异步结果的账号作用域与发布次序](2026-11-12-async-state-stale-result-ordering.md)。
