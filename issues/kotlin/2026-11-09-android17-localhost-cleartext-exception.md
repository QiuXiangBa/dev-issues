---
title: "Android 17 隐式回环配置会绕过全局明文禁用"
stack: "kotlin"
platform: [android]
versions: ["Android 17 / API 37.1 emulator", "Android 7.0 / API 24 emulator", "targetSdk 36", "AGP 8.11.1", "OkHttp 4.12.0"]
tags: [android17, network-security-config, cleartext, localhost, loopback, ipv6, okhttp, instrumentation]
project: "android"
status: solved
date: "2026-11-09"
---

## 现象

应用希望全面禁止 HTTP，已经在 `AndroidManifest.xml` 中设置 `android:usesCleartextTraffic="false"`，并引用以下网络安全配置：

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
</network-security-config>
```

在 Android 7 / API 24 上，普通域名和回环地址的 HTTP 都被拦截。但在 Android 17 / API 37.1 上，同一份配置出现以下差异：

- 普通域名的 `NetworkSecurityPolicy.isCleartextTrafficPermitted(host)` 返回 `false`。
- `localhost`、`127.0.0.1` 的查询返回 `true`。
- 在目标 App 进程内，平台 `HttpURLConnection` 和 App 自带的默认 OkHttp 均能请求本地 HTTP 测试服务并收到 `200`。

因此，XML 中存在 `base-config=false`、普通域名被拦截，不能单独作为所有目的地址均禁止明文的验收依据。实测应用的 `targetSdk` 是 36，不能仅按 `targetSdk < 37` 排除此问题。

## 原因

Android 17 新增了隐式 localhost 配置：如果没有显式定义回环地址的配置，系统会注入一份允许明文的配置。它还不强制证书透明度和证书固定，但信任锚点继承 `base-config`；这不等于无条件信任所有 HTTPS 证书。见[官方 localhost 说明](https://developer.android.com/privacy-and-security/security-config#localhost)。

系统识别的回环目标包括 `localhost`、`ip6-localhost`，以及被判断为 loopback 的数字 IP，例如 `127.0.0.1`、`::1`。

对照 Android 17 的 AOSP 实现：

1. `XmlConfigSource.parseNetworkSecurityConfig()` 遍历显式域配置，只要任意一个 `Domain.isLocalhost()` 为真，就将统一的 `isLocalhostDefined` 标记置为真。
2. 只有未定义该标记且相关平台功能开启时，才创建 `mLocalhostConfig`。
3. `ApplicationConfig.getConfigForHostname()` 先匹配显式域，再匹配隐式 localhost；两者都未命中时回落到全局配置。

所以只需显式配置一个 `localhost`，即可阻止整份隐式回环配置的注入；无需逐个穷举 IPv4 / IPv6 回环地址。其余未单独配置的回环地址会回落到禁止明文的 `base-config`。如果工程另有 `cleartextTrafficPermitted="true"` 的显式域规则，仍需一并检查，不能靠本修复抵消它们。

## 解决方案

Manifest 的 `<application>` 同时声明：

```xml
android:usesCleartextTraffic="false"
android:networkSecurityConfig="@xml/network_security_config"
```

`res/xml/network_security_config.xml` 使用：

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
    <!-- Prevent Android 17 from adding an implicit cleartext exception for loopback addresses. -->
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="false">localhost</domain>
    </domain-config>
</network-security-config>
```

`includeSubdomains="false"` 与不填写时的默认匹配语义一致；显式填写可满足本次 AGP 8.11.1 的 Lint 检查。省略时实际出现：

```text
Error: Missing includeSubdomains attribute [NetworkSecurityConfig]
```

这次修复只收紧明文策略，不引入自定义 CA、调试信任证书、放宽主机名校验或全信任证书实现。使用的 XML 元素也能由 Android 7 解析。

### 验证方法

1. 核对 Debug / Release 合并后的 Manifest 以及最终 APK 的二进制 Manifest、打包 XML；资源压缩可能重命名 XML 文件路径，需要根据资源表定位，不能只凭 ZIP 中是否存在原文件名判断。
2. 在目标 App 的 UID / 进程里运行 instrumentation，查询全局策略和以下主机策略，预期全部为 `false`：

   ```kotlin
   val policy = NetworkSecurityPolicy.getInstance()
   check(!policy.isCleartextTrafficPermitted())
   listOf(
       "example.com", "localhost", "ip6-localhost",
       "127.0.0.1", "127.0.0.2", "::1", "[::1]",
   ).forEach { host -> check(!policy.isCleartextTrafficPermitted(host)) }
   ```

3. 启动临时本地 HTTP 和自签名 HTTPS 服务，通过 `adb reverse` 映射到设备。分别用平台 URLConnection 和目标 APK 自带的默认 OkHttp 发请求：HTTP 必须以明确的 cleartext policy 错误失败；自签名 HTTPS 必须以证书信任错误失败，连接拒绝、DNS 错误或超时不算通过。
4. 再访问证书正常的 HTTPS 服务，确认 TLS 握手成功。探针访问受保护接口得到 `401` 仍能证明 TLS 已建立；账号登录需另行验证，不能把 `401` 当成登录成功。
5. 同时在旧系统和 Android 17 复测；普通主机策略、全局策略和真实请求缺一不可，不能只在测试进程或另一个包名中测自己的配置。

### 本次实测结果与边界

| 配置 | Android 7 / API 24 | Android 17 / API 37.1 |
|---|---|---|
| 只有全局明文禁用 | 第一版 13 项通过 | 第一版 9 项通过、4 项失败；回环 HTTP 实际返回 200 |
| 全局禁用并显式 localhost 禁用 | 扩展后 17 项全部通过 | 扩展后 17 项全部通过 |

最终检查涵盖目标进程身份、Manifest 标志、全局 / 主机策略，以及两种网络栈的 HTTP 拒绝、有效 HTTPS 连通和自签名证书拒绝。Debug / Release 构建、Lint 均通过。本次运行时验证来自两台平板模拟器，没有真机验证；结论适用于遵守 Android 网络安全策略的已测网络栈，不把原生 socket 或独立 TLS 实现视为已覆盖。

## 相关链接

- [Android 官方：Localhost configuration](https://developer.android.com/privacy-and-security/security-config#localhost)
- [AOSP Android 17：XmlConfigSource，显式 localhost 判断与隐式配置注入](https://android.googlesource.com/platform/external/conscrypt/+/refs/heads/android17-release/nsc/src/android/security/net/config/XmlConfigSource.java#420)
- [AOSP Android 17：ApplicationConfig，按主机选择配置及全局回落](https://android.googlesource.com/platform/external/conscrypt/+/refs/heads/android17-release/nsc/src/android/security/net/config/ApplicationConfig.java#136)
- [Android 官方：Manifest usesCleartextTraffic 与 Network Security Config 的优先关系](https://developer.android.com/guide/topics/manifest/application-element#usesCleartextTraffic)
