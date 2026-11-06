---
title: "MetricKit 崩溃诊断拿不到 Objective-C 异常原文（exceptionReason 恒为空）"
stack: "swift"
platform: [ios]
versions: [ios 27.0.1, xcode 27.1, ios 16.0 deployment target]
tags: [metrickit, crash-reporting, nsexception, diagnostics, ios27]
project: "tutuai"
status: workaround
date: "2026-11-06"
---

## 现象

用 MetricKit 收集崩溃，期望从诊断里拿到未捕获 Objective-C 异常的消息（`CrashDiagnostic.exceptionReason` / 旧接口 `MXCrashDiagnostic.exceptionReason`，iOS 17 起提供，含 `composedMessage`、`formatString`、`arguments`、`exceptionName`）。

真机（iPad，iPadOS 27.0.1）实测，下面几种组合下这个字段**全部为空**：

- 抛法：`NSException(name:reason:userInfo:).raise()`，以及 `NSException.raise(_:format:arguments:)`（`raise:format:`）
- 构建：Debug、Release
- 接口：iOS 27 新接口 `MetricManager().diagnosticReports`，以及旧接口 `MXMetricManagerSubscriber.didReceive(_: [MXDiagnosticPayload])`（在 27 上强制走旧接口也一样）

诊断里能拿到的内容：

- `terminationReason`：`"Namespace SIGNAL, Code 0x6"`
- `signal`：6（SIGABRT）
- `exceptionType`：10（EXC_CRASH）
- `terminationCategory`：`abnormal`（新接口才有）
- `callStackTree`：调用栈，崩溃线程里能看到 `objc_exception_throw` 及抛异常的调用方

旧接口 JSON 的 `diagnosticMetaData` 里也没有 `objectiveCexceptionReason`。

## 原因

文档对这个字段的说明是「if available」，没写什么情况下才有。实测系统在上述组合下都不填，原因不明。其他系统版本会不会填，没有验证。

## 解决方案

不要指望 MetricKit 给出异常原文，排查靠调用栈：

1. 崩溃线程里 `objc_exception_throw` 往下第一个调用方，就是抛异常的位置。系统框架内部抛的，看它下面最近一帧自己的代码。调用栈需要符号化，见同库「MetricKit 调用栈只有地址，借同芯片同系统版本设备的 DeviceSupport 符号用 atos 还原」。
2. 确实要异常消息，可以自己用 `NSSetUncaughtExceptionHandler` 把 `exception.name`、`reason`、`callStackSymbols` 写到本地文件（不要在处理函数里发网络请求），下次启动再随报告一起上传。这一条没有实测；它也抓不到 Swift 运行时 trap（数组越界、强制解包等，这类是 SIGTRAP，`exceptionType` 6）。

顺带记几条实测过的 MetricKit 行为：

- **送达时机**：崩溃诊断在崩溃后下一次启动时送达，实测几秒内到，不是同步的崩溃回调。新接口同一次崩溃只送一次，再启动不会重放。模拟器不产生诊断，只能在真机验证。
- **新旧接口**：iOS 27 SDK 的新接口是 `MetricManager().diagnosticReports`（`AsyncSequence<DiagnosticReport, Never>`），`report.result` 是 `.crash(CrashDiagnostic)` / `.hang` / … 枚举，另有 `environment`、`timeRange`；这些类型都是 `Codable`，用 `JSONEncoder` 转 JSON。旧类型只标了 `API_TO_BE_DEPRECATED`，部署目标低于 27 时编译不报警告，27 上旧接口也仍然送达。部署目标低于 27 的写法：

```swift
if #available(iOS 27.0, *) {
    let manager = MetricManager()
    Task.detached {
        for await report in manager.diagnosticReports {
            guard case .crash(let crash) = report.result else { continue }
            let json = try? JSONEncoder().encode(crash)
            // 落盘，下次联网再传
        }
    }
} else {
    MXMetricManager.shared.add(subscriber)   // didReceive 里先同步取 jsonRepresentation()
}
```

- **两套 JSON 字段名不同**：旧接口是 `callStackTree.callStacks[].callStackRootFrames` 加 `diagnosticMetaData`；新接口是 `callStackTree.callStackThreads[].rootFrames`，环境信息在 `DiagnosticReport.environment`。两套都有 `threadAttributed` 标出崩溃线程。
- **系统名**：iPad 上的系统名也报成 `iPhone OS`（例如 `iPhone OS 27.0.1 (24A446)`）。给人看的地方要自己改称 iPadOS。

## 相关链接

- https://developer.apple.com/documentation/metrickit
- https://developer.apple.com/documentation/metrickit/mxcrashdiagnostic/exceptionreason
