---
title: "新 Xcode 可部署旧 iOS 却无法操作真机，XCTest 还需匹配旧运行库"
stack: "swift"
platform: ["ios"]
versions: ["Xcode 27.2", "Xcode 26.6", "iPadOS 15.8.8", "pymobiledevice3 11.50.3", "WebDriverAgent 10.2.2"]
tags: ["xcode", "ios15", "device-support", "xcuitest", "webdriveragent", "usbmux", "mach-o"]
project: "ios-compatibility-example"
status: "workaround"
date: "2026-11-10"
---

## 现象

App 可以按 iOS 15.8 deployment target 构建，旧 iPad 也能运行已装应用，但新 Xcode 的设备工具、CoreDevice 或依赖它的设备控制工具无法操作该设备，显示 unsupported 或不可用。

把 UI 测试 runner 的 target 也改成 15.8 后仍可能无法启动，因为嵌入的 XCTest/XCUIAutomation 预编译运行库要求更高系统。

## 原因

Xcode 支持表将 deployment target 与 device support 分列：能构建给旧系统运行的 App，不等于当前安装/调试/自动化工具支持该系统。

本次实测 Xcode 27.2 的相关 XCTest/XCUI 运行库 Mach-O 要求 minos 17.0；Xcode 26.6 所带对应旧运行库可用于目标旧系统。源码的 deployment target 不会重写预编译二进制的最低系统要求。

因此不能仅凭 unsupported 判断设备没有信任电脑、未配对或处于恢复模式，也不能靠删除缺失库来“修好”测试 runner。

## 解决方案

### 1. 分别核实设备、App 与测试工具链

先确认真实系统、机型、既有配对、已安装 App 的 bundle/version/minimum OS。测试入口与已安装业务 App 分开处理；App 已装好不意味着测试 runner 已签名、已包含此设备。

保留全局 Xcode 选择，用命令级环境变量选择经 Apple 官方分发并验签的旧 Xcode：

```bash
env -u CPATH \
  DEVELOPER_DIR=/path/to/OlderXcode.app/Contents/Developer \
  xcodebuild -project WebDriverAgent.xcodeproj \
  -target WebDriverAgentRunner -configuration Debug -sdk iphoneos \
  clean build ARCHS=arm64 IPHONEOS_DEPLOYMENT_TARGET=15.8 \
  CODE_SIGNING_ALLOWED=NO \
  SYMROOT=/tmp/legacy-wda-build/Products \
  OBJROOT=/tmp/legacy-wda-build/Intermediates
```

这是本次 WDA 10.2.2 的构建路径示例，具体目标和选项应以所固定源码版本为准。`env -u CPATH` 只作用于该次命令，用于排除本机 include 路径污染；不要改全局环境来掩盖警告。若旧 Xcode 的 generic build-for-testing 要求未安装的新平台组件，先核对 target build 与真实依赖，不盲目安装全部组件。

### 2. 对完整 runner 做静态审计，再实际启动

- 保留 runner、xctest plugin、完整 XCTest/XCUI/Testing/SwiftTesting 等实际依赖；只从同一套已核验工具链补齐缺失依赖。
- 用 `xcrun vtool -show-build <binary>`、`otool -l <binary>` 看所有嵌入 Mach-O 及每个 slice 的最低系统；用 `otool -L <binary>` 核对非系统 `@rpath` 依赖闭包。
- target 降版和“主可执行 minos 合格”都不能代替逐依赖检查；面向新系统的预构建 WDA 包可能省略旧系统仍需的测试运行库。
- 静态依赖审计通过不代表所有系统符号和业务路径均已验证。最终必须在目标设备实际启动 XCTest/WDA 并取得 ready/HTTP 状态。

本次组合经旧 USB 服务、匹配的旧 DeveloperDiskImage、有效既有配对及正规开发签名，在 iPadOS 15.8.8 实际运行成功。遇到配对/信任失败应走正常设备流程，不通过重新配对、提升设备管理权限或绕过门禁强行推进。

### 3. 签名和通信只授予测试所需范围

runner 使用独立 bundle，描述文件包含目标设备，App ID 前缀、团队和实际签名证书相符。测试业务 App 可以保留原安装，也可在明确授权下单独更新；两者的构建来源要分别记录。

优先通过 USB 转发并将主 HTTP 服务限于回环地址。WDA 的主 HTTP 与 MJPEG broadcaster 可能使用不同监听配置，不能以 `USE_IP` 只约束了其中一个就宣称全部监听都安全；核对当前版本实现并关闭或限制不需要的服务。结束后关闭服务、停止转发/日志采集，清理本次 runner。

### 4. 将工具观察误差与产品行为分开

- 本例旧设备在 runner-ready 握手后仍等了一段时间才开始测试。只看到一条 INFO 暂时不变，不能立即判死锁。
- 老系统 AX/source 快照可能慢、首次漏掉呈现页面，或者仍列出 opacity=0 的控件。以近期实屏、实际控件显隐和后续状态交叉核对；先唤出自动隐藏控件，再点关闭。
- 用 Power 事件唤亮屏幕并复核仍处于锁定状态；Home 可能触发解锁。设备要求 Touch ID/密码时由用户完成，不代填、猜测或绕过。
- 后台音频测试记下 A 歌，保持锁定/后台跨自然结尾，在重新激活 App 前确认标题变 B；稍后回 App 核对实际下一首进度。锁屏时钟或播放图标本身不能证明实际音频输出。
- 多个安装包/进程使用同一测试账号或竞争音频会话，会影响登录与播放。对照进程和中断日志，受干扰的一轮不计通过；重新取得独立证据。
- 原始测试包版本号相同不证明源提交相同。可读取运行中主映像 UUID 与归档关联，但源 commit 仍需构建记录；自己的新构建则保留源 SHA、UUID、IPA hash 与 dSYM。

此记录是已验证工具组合的回退路径，不代表新 Xcode 已恢复对旧设备的支持，也不保证任意 pm3/WDA 命令均兼容所有旧系统。

## 相关链接

- [Apple Xcode 系统要求及支持表](https://developer.apple.com/xcode/system-requirements)
- [Appium WebDriverAgent](https://github.com/appium/WebDriverAgent)
- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3)
- [Release 开发签名与升级核验](2026-11-10-ios-release-development-signing-validation.md)
