---
title: "SwiftUI 网络图片优先用 Kingfisher：AsyncImage 无磁盘缓存、无失败占位与取消"
stack: "swift"
platform: [ios]
versions: [xcode 27.0, "ios 18.6 simulator", swiftui, "kingfisher 8.12.0"]
tags: [swiftui, asyncimage, kingfisher, image-cache, network-image, spm, xcodegen, placeholder]
project: "tutuai"
status: solved
date: "2026-09-17"
---

## 现象

列表 / 横向轨道里的卡片封面用系统 `AsyncImage(url:)` 加载，功能上「能用」，但验收时发现：

- 切换分页（换周）或退出再进页面，所有封面重新走网络下载，弱网下卡片先空一阵再出图；
- 没有封面（URL 为 nil / 空串）、加载中、加载失败三种情况都得自己在 `phase` 里分支处理，一不小心就回落到设计稿的示意插画，让用户误以为那是真实内容；
- 横向滚动时滚出视口的卡片不会取消下载。

没有报错，是能力缺口，不是 bug。

## 原因

`AsyncImage` 是最小实现：只依赖 `URLSession.shared` 的默认 URLCache（内存为主、受 HTTP 缓存头支配、进程重启不保证命中），没有独立的磁盘缓存层，没有失败重试、过渡动画、取消策略，也没有解码后的下采样。它适合 demo，不适合任何有多张网络图片的列表页。

## 解决方案

**规则：只要页面有多张网络图片（列表、轨道、封面墙），一开始就用 Kingfisher，不要先写 `AsyncImage` 再换。** 单张一次性的大图（比如详情页 hero 图）用 `AsyncImage` 可以接受。

1. 加 SPM 依赖。XcodeGen 项目写在 `project.yml`（`.xcodeproj` 不入库时 `Package.resolved` 也不入库，靠 `from:` 约束版本）：

   ```yaml
   packages:
     Kingfisher:
       url: https://github.com/onevcat/Kingfisher.git
       from: "8.12.0"
   targets:
     <app>:
       dependencies:
         - package: Kingfisher
   ```

   然后 `xcodegen generate`，首次 `xcodebuild` 会自动 resolve。

2. 视图层用 `KFImage`，占位符用中性图形（灰底 + `photo` SF Symbol），不要回落设计稿插画：

   ```swift
   import Kingfisher

   KFImage(url)                       // url 为 nil 时直接显示 placeholder
       .placeholder {
           ZStack {
               Color(.systemGray5)
               Image(systemName: "photo").font(.system(size: 56))
           }
       }
       .cancelOnDisappear(true)       // 滚出视口取消下载
       .fade(duration: 0.25)
       .resizable()
       .scaledToFill()
       .frame(width: w, height: h)
       .clipShape(RoundedRectangle(cornerRadius: r))
   ```

   加载失败时 `KFImage` 不会换成别的图，占位符继续留着，等于失败态免费得到；需要区分时再加 `.onFailureImage(_:)`。

3. 后端字段是空串而不是 null 时，在 DTO 映射里先转成 nil：`coverUrl.flatMap { $0.isEmpty ? nil : URL(string: $0) }`，否则 `URL(string: "")` 得到 nil 还好，但 `URL(string: " ")` 之类会变成一个必然失败的请求。

4. 缓存默认：内存 + 磁盘（`~/Library/Caches/com.onevcat.Kingfisher.ImageCache.default`），磁盘 7 天过期、无大小上限。列表封面一般不用调；头像等会变更的图给 URL 带版本号或用 `.forceRefresh()`。

## 相关链接

- Kingfisher：https://github.com/onevcat/Kingfisher
- 落地 PR（含 XcodeGen 依赖写法与占位符）：https://github.com/QiuXiangBa/tutuai-app/pull/44
