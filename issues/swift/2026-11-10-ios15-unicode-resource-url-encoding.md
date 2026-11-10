---
title: "iOS 15/16 的原始中文资源 URL 解析失败，导致图片空白或音频被当作未配置"
stack: "swift"
platform: ["ios"]
versions: ["iPadOS 15.8.8", "iOS 17 SDK and later", "Xcode 27.2", "Kingfisher 8.15.0"]
tags: ["ios15", "foundation", "url", "unicode", "percent-encoding", "cfurl", "kingfisher"]
project: "ios-compatibility-example"
status: "solved"
date: "2026-11-10"
---

## 现象

同一个服务端响应在现代系统显示正常，在 iOS 15/16 上却出现大批图片占位、可选头像整行为空，或提示音频“未配置”。对照资源中纯 ASCII 地址可用，带原始中文文件名的地址失败。

这是 DTO 层就可能发生的问题：`URL(string:)` 返回 nil 时，图片字段变空；若头像 DTO 用 `guard let url` 后 `compactMap`，整个选项会被丢弃，连可点击节点都没有。无需等到下载器报错。

## 原因

Apple 对链接到 iOS 17 及后续 SDK 的应用在新系统上更新了 URL 解析和非法字符编码行为。旧系统不能按现代宿主的行为接受原始中文、空格等字符。新 Mac 上 `URL(string:)` 成功，并不能证明 iOS 15 上成功。

直接把所有图片失败归因于 WebP/AVIF 支持会走偏：本次抽查的失败样本经正确编码后实际返回 JPEG/PNG，字节特征及 ImageIO 解码均正常。排查时应把原始字符串、URL 构造、HTTP 状态、实际格式和图像解码分层核对。

## 解决方案

### 1. 在共享层统一服务端素材地址入口

适用范围是 ASCII 域名、资源路径/查询等包含原始 Unicode 或空格的 URI；国际化域名的 IDNA、特殊 scheme 和业务安全策略另行处理。它补足编码，不充当 scheme/host 安全校验器。

```swift
import CoreFoundation
import Foundation

enum RemoteAssetURL {
    static func make(_ text: String?) -> URL? {
        guard let text, !text.isEmpty else { return nil }
        if #available(iOS 17, macOS 14, *) {
            return URL(string: text)
        }
        return legacyURL(from: text)
    }

    static func legacyURL(from text: String) -> URL? {
        guard !text.isEmpty,
              let encoded = text.addingPercentEncoding(withAllowedCharacters: uriCharacters),
              let url = CFURLCreateWithString(nil, encoded as CFString, nil) else { return nil }
        return url as URL
    }

    // RFC 3986 unreserved + reserved，保留现有百分号转义。
    private static let uriCharacters = CharacterSet(charactersIn:
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~:/?#[]@!$&'()*+,;=%")
}
```

保留 URI 分隔符与现有 `%2F`、`%20` 等转义，只编码其余非法字符；旧分支再经 CFURL 校验，使裸 `%`、截断或错误转义仍失败。17+ 保留既有 native 行为，避免本次修复无意改变现代系统的解析规则。

不要先全量解码再编码，也不要对整串 URL 使用不保留 URI 分隔符的 CharacterSet。在本机混合中文与已有转义的探针中，直接经某些 URLComponents 构造路径会把 `%2F` 再编码为 `%252F`；不能以纯中文样本通过就认定不会双编码。

将共享方法用于封面、头像、音频、视频、绘本图片数组、兼容字段候选键及上传结果地址。保留字段去空白、候选键顺序、失败后尝试下一字段及上传结果无地址时的原有错误。API 路由、固定外链、鉴权和业务完成上报不需要随此修复改动。

### 2. 在现代宿主上直接验证旧分支

```swift
let raw = "https://example.com/books/封面.jpg"
precondition(CFURLCreateWithString(nil, raw as CFString, nil) == nil)
let encoded = RemoteAssetURL.legacyURL(from: raw)!.absoluteString
precondition(encoded == "https://example.com/books/%E5%B0%81%E9%9D%A2.jpg")
precondition(RemoteAssetURL.legacyURL(from: encoded)?.absoluteString == encoded)
```

回归集至少包括：中文、空格、纯 ASCII、已编码中文、原始中文混合 `%2F/%20`、query/fragment、带端口的 IPv6，以及空串、裸 `%`、`%2`、`%ZZ`。检查二次构造幂等；带签名的查询参数要保持现有转义与大小写。旧解析器基准断言和期望的编码结果都要验证，不能只测“现代 URL 构造成功”。

本次另外对既有可解析 ASCII 地址作对照，结果未变，并在 iPadOS 15.8.8 真机验证图片、头像、中文地址绘本阅读和儿歌音频恢复。没有遍历全部资源或证明每种媒体编码都可解码。

## 相关链接

- [Apple URL.init(string:)](https://developer.apple.com/documentation/foundation/url/init(string:))
- [RFC 3986 URI 语法](https://www.rfc-editor.org/rfc/rfc3986)
- [Kingfisher FAQ](https://github.com/onevcat/Kingfisher/wiki/FAQ)
- [iOS 15 页面与等待回退](2026-11-10-ios15-swiftui-concurrency-backdeployment.md)
