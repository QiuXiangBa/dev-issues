---
title: "Debug 包连测试环境、Release 包连生产环境：真机上的后端业务报错在模拟器复现不出来"
stack: "common"
platform: [ios, android]
versions: [xcode 27.0, ios 16.0+, android targetsdk 36]
tags: [environment, base-url, debug, release, build-config, backend, code-600, simulator, real-device, testflight]
project: "tutuai"
status: solved
date: "2026-10-26"
---

## 现象

用户在真机（TestFlight / 商店包）上打开某个页面，直接落到失败态，屏幕上是一句后端业务校验文案 + 「重试」。在本机模拟器上用同一账号类型、同一页面怎么都复现不出来：列表接口、详情接口全部 200，几百条数据逐条拉也没有一条失败。

这句文案在两端客户端源码里 grep 不到，说明它是后端返回的 `msg`（HTTP 200 + `code 600`），客户端只是把 `msg` 原样显示。

## 原因

两个端的网络层都按构建类型切后端：

```swift
// iOS
enum APIConfig {
    #if DEBUG
    static let baseURL = "https://api-test.example.com"   // 测试环境
    #else
    static let baseURL = "https://api.example.com"        // 生产环境
    #endif
}
```

```kotlin
// Android
val BASE_URL = if (BuildConfig.DEBUG) "https://api-test.example.com" else "https://api.example.com"
```

模拟器跑的是 Debug 包 → 测试环境；真机装的是 Release / TestFlight / 商店包 → 生产环境。两套后端的业务数据一模一样（同一批内容同步过去的），但**后端配置不一样**：生产环境的某项服务端配置（本例是素材库的对象存储地址）和数据里的资源地址对不上，服务端在出详情时校验不过就返回业务错误；测试环境配置是对的，所以全通。

账号也是分环境的：模拟器上的登录态是测试环境的 token，拿去请求生产一律 401，所以不能直接「把模拟器指向生产再看」。

## 解决方案

客户端无事可做，是后端生产配置问题，交后端修。排查上的可复用做法：

1. **先分环境**。真机 / 审核反馈的接口类报错，第一件事看 `APIConfig` / `ApiConfig` 这类 base URL 配置是不是按 `#if DEBUG` / `BuildConfig.DEBUG` 切环境。是的话，模拟器复现不出来基本就是环境差异，不要再在测试环境上绕。
2. **错误文案先 grep 客户端源码**。grep 不到就是后端 `msg` 原样透传，根因在服务端或服务端配置，客户端不用改。
3. **拿一个生产环境的测试账号，脚本化登录 + 遍历接口**（python `urllib` 即可，token 只留在内存）：登录 → 翻完列表所有分页 → 逐条拉详情 → 统计 `code != 200` 的条目和 `msg`。几百条一两分钟跑完，一眼看出是「全部失败」（配置问题）还是「个别失败」（数据问题）。把同一脚本指向测试环境跑一遍做对照，再把两边的数据（id、资源地址）逐条 diff，就能把「数据一样、只有配置不同」这个结论坐实。
4. 想在模拟器上看真实画面：临时加启动参数覆盖 base URL（`--api-base=<url>`），并用接口直接登录把 token 写进 Keychain，装到一台**没有登录态**的模拟器上跑，别覆盖日常验收机上的测试环境登录态；跑完 `simctl uninstall` + `simctl keychain <udid> reset` 清掉生产 token。
5. 顺手核一遍生产配置里有没有从测试环境复制过来没改的项（本例还发现生产 bootstrap 里一个资源地址仍指向测试域名）。

另外注意：Debug 包临时指向生产时，Debug 下任何「兜底 token」「写死的 Authorization 头」会先把你挡在公开接口外（见相关链接）。

## 相关链接

- `issues/swift/2026-10-14-debug-hardcoded-token-public-endpoint-401.md`：Debug 包写死的兜底 Authorization 头在生产网关上 401（本次排查时一起踩到，已追加更新）
- `issues/swift/2026-09-08-simulator-keychain-token-persists.md`：模拟器 Keychain token 跨安装残留
