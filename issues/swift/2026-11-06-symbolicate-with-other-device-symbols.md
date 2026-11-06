---
title: "MetricKit 调用栈只有地址，借同芯片同系统版本设备的 DeviceSupport 符号用 atos 还原"
stack: "swift"
platform: [ios]
versions: [ios 27.0.1, xcode 27.1]
tags: [metrickit, symbolication, atos, dsym, device-support, crash-reporting]
project: "tutuai"
status: solved
date: "2026-11-06"
---

## 现象

MetricKit 崩溃诊断的 `callStackTree` 里，每一帧只有 `binaryUUID`、`address`、`offsetIntoBinaryTextSegment`（旧接口 JSON 还带 `binaryName`；新接口的二进制名在 `callStackTree.binaryInfo` 里按 UUID 查），没有函数名。

崩溃发生在 iPad（`iPad12,1`，iPadOS 27.0.1，build 24A446）。本机 `~/Library/Developer/Xcode/iOS DeviceSupport/` 里只有一台 iPhone 同系统版本的符号（`iPhone12,3 27.0.1 (24A446)`），没有这台 iPad 的。看起来系统框架帧还原不了。

## 原因

系统框架（UIKitCore、CoreFoundation、libobjc 等）的二进制按「系统 build 号 + CPU 架构切片」构建。芯片相同、系统 build 号相同的设备，用的是同一批框架二进制，UUID 完全一致。iPad 9 和 iPhone 11 Pro 都是 A13，同为 24A446 时，18 个二进制的 UUID 全部对得上。所以别的设备的 DeviceSupport 也能用。

判断依据只有 UUID：`dwarfdump --uuid` 结果和诊断里的 `binaryUUID` 一致，就能用。

## 解决方案

1. **展开调用栈**：崩溃诊断里每个线程的 `rootFrames[0]`（旧接口 `callStackRootFrames[0]`）是栈顶，`subFrames[0]` 是它的调用方，一路往下到 `start`。
2. **找二进制，并用 UUID 核对**：
   - 系统框架：在 `~/Library/Developer/Xcode/iOS DeviceSupport/<机型> <系统版本> (<build>)/arm64e/Symbols/` 下按名字 `find`。同名可能有多个，比如 `SwiftUI` 在 `AccessibilityBundles` 里也有一个，要用 `dwarfdump --uuid` 挑出 UUID 和 `binaryUUID` 相同的那个。
   - App 自己：用同一次构建的产物或归档里的 dSYM，同样核对 UUID。Debug 构建开了 `ENABLE_DEBUG_DYLIB` 时，代码在 `<App>.app/<App>.debug.dylib` 里，不在主可执行文件里。
3. **用 atos 还原**：加载地址 = `address - offsetIntoBinaryTextSegment`。

```bash
atos -o "<二进制路径>" -arch arm64e -l 0x<加载地址> 0x<address>   # App 自己的切片一般是 arm64
```

4. 批量处理写个小脚本：按 UUID 建「UUID → (路径, 架构)」表，逐帧调 atos，输出和 .ips 相近的线程列表。核心逻辑：

```python
def chain(frame):                      # 展开一条线程
    out = []
    while frame:
        out.append(frame)
        subs = frame.get('subFrames') or []
        frame = subs[0] if subs else None
    return out

load = f['address'] - f['offsetIntoBinaryTextSegment']
subprocess.run(['atos', '-o', path, '-arch', arch, '-l', hex(load), hex(f['address'])])
```

几个坑：

- 私有符号被剥掉的帧，atos 会给出最近的导出符号，名字对不上而且偏移是 `+ 0`。例如实际在 `-[NSException raise]` 里的帧，被显示成 `-[CFPrefsDaemon listener] + 0`。看到「无关名字 + 0」要当成不可信。
- 有些框架（如 `Gestures`）没有符号，只能看到地址。
- 线上包要还原 App 自己的帧，必须保留每个提交审核归档的 dSYM。DeviceSupport 只有在 Xcode 连过对应系统版本的设备后才会下载。手头没有同型号设备，就找同芯片、同系统版本的设备连一次。

## 相关链接

- https://developer.apple.com/documentation/xcode/adding-identifiable-symbol-names-to-a-crash-report
- https://developer.apple.com/documentation/metrickit/mxcallstacktree
