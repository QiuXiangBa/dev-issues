---
title: "模拟器 Keychain 中的 mock token 跨构建残留导致 live 构建 401 登出"
stack: swift
platform: [ios]
versions: [xcode 26.6, ios 18.6 simulator, ios 26.5 simulator]
tags: [simulator, keychain, mock, auth, 401, simctl]
project: xuejieai
status: solved
date: 2026-09-08
---

## 现象

App 用 Keychain 保存登录 token。为了走查一个需要特定后端数据的页面，在模拟器上装了一个开启 mock 后端的构建，并通过启动环境变量把占位 token 写进 Keychain：

```bash
SIMCTL_CHILD_APP_SEED_TOKEN=mock-token xcrun simctl launch <udid> <bundle-id>
```

走查结束后用 `xcrun simctl install` 装回连真实后端的构建，App 启动后第一个请求就 401，直接被踢回登录页。

## 原因

Keychain 不属于 App 沙盒数据。同一个 bundle id 覆盖安装不会清 Keychain，`mock-token` 留在模拟器里，真实后端自然拒绝。

模拟器上「装干净构建仍保持登录」本来是方便点，但一旦在同一台模拟器上切换过后端环境，残留的 token 就变成脏数据。

## 解决方案

三选一，按省事程度排：

1. **一台模拟器只跑一种后端环境**。例如一台一直装 live，另一台一直装 mock，互不污染。
2. **切回 live 前重新种入有效 token**。同一套环境变量注入方式再启动一次即可。种 token 的代码只临时加在 App 入口，构建完立刻 `git checkout` 还原，绝不进 commit，也不要把 token 硬编码进源码：

   ```swift
   // 临时代码，仅本地走查用
   if let seed = ProcessInfo.processInfo.environment["APP_SEED_TOKEN"] {
       TokenStore.shared.save(seed)
   }
   ```

3. **App 侧防御**：把 token 和后端环境标识（`mock` / `live` / base URL）一起存进 Keychain，启动时发现环境标识和当前构建不一致就丢弃 token。这样切环境永远不会带着旧 token 发请求。

`xcrun simctl erase <udid>` 也能清干净，但会抹掉整台模拟器的数据，代价最大。

## 相关链接

- https://developer.apple.com/documentation/xcode/running-your-app-in-simulator-or-on-a-device
