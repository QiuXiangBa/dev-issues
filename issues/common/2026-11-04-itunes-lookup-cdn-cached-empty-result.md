---
title: "App Store 查询接口 itunes.apple.com/lookup 偶发返回 0 条：CDN 节点缓存了空结果"
stack: "common"
platform: [ios]
versions: ["iTunes Search API lookup (2026-11)"]
tags: [itunes-lookup, app-store, version-check, update-prompt, cdn, akamai, cache-busting]
project: "tutuai"
status: solved
date: "2026-11-04"
---

## 现象

App 内的版本检查调 `https://itunes.apple.com/lookup?id=<APP_ID>&country=cn`，用商店返回的 `version` 和本机 `CFBundleShortVersionString` 比较。同一个 URL 偶尔会返回空结果：

```json
{"resultCount":0,"results":[]}
```

HTTP 状态是 200，没有任何报错。代码把它当成「没有新版本」，所以那次启动不会弹提示。

2026-11-04 实测，不带额外参数连查 8 次，有 2 次是 0 条：

| 结果 | `cache-control` | `x-cache` |
|---|---|---|
| 0 条 | `max-age≈1100`（约 18 分钟） | `TCP_HIT from a23-204-92-*.deploy.akamaitechnologies.com` |
| 1 条 | `max-age` 从 86400 往下递减 | `TCP_HIT` / `TCP_MEM_HIT` |

## 原因

接口前面挂着 Akamai CDN，缓存键是完整 URL。部分边缘节点缓存了一份空结果，请求落到这些节点上就会拿到 0 条。空结果的缓存时间较短（约 20 分钟），正常结果约 24 小时。

为什么会缓存到空结果，没有官方说明。推测是 App 在该区刚上架或刚能搜到时，某次查询拿到的空结果被缓存了下来。

另外，正常结果也会被缓存将近 24 小时，所以新版本上架后的一段时间里，不同节点返回的版本号也可能不一致。

## 解决方案

1. **每次请求带一个随机参数，绕开 CDN 缓存直接回源**。实测加参数后连查 8 次都是 `TCP_MISS`、`max-age=86400`，每次都拿到 1 条：

   ```swift
   var components = URLComponents(string: "https://itunes.apple.com/lookup?id=<APP_ID>&country=cn")!
   components.queryItems = (components.queryItems ?? []) + [URLQueryItem(name: "_t", value: String(Int(Date().timeIntervalSince1970)))]
   let (data, _) = try await URLSession.shared.data(from: components.url!)
   ```

   其他语言同理，在查询串末尾加 `&_t=<时间戳>` 即可。

2. **0 条或解析失败时按「没有更新」处理**，不要拦住启动流程。

3. **必须带 `country=<区>`**。不带时默认查美区，App 没上架美区就永远返回 0 条。这种 0 条加随机参数也解决不了。

4. **新版本上架后不要马上提示**。用户设备上 App Store 里的商店页可能还没刷新出新版本，用户点了「更新」，看到的仍是「打开」。可以用返回的 `currentVersionReleaseDate` 判断，上架满 1 天再提示。开源库 Siren 有同样用途的配置 `showAlertAfterCurrentVersionHasBeenReleasedForDays`。

5. **排查方法**：用 `curl -s -D - "<url>" -o body.json` 连跑多次，对比带和不带随机参数时的 `cache-control`、`x-cache` 和 `resultCount`。

## 相关链接

- iTunes Search API（lookup）文档：https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/
- Siren（iOS 版本更新提示库）：https://github.com/ArtSabintsev/Siren
