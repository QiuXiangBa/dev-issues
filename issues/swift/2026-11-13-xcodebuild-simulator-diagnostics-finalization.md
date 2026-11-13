---
title: "Xcode UI 测试通过后等待模拟器诊断，xcresult 无法完成归档"
stack: "swift"
platform: ["ios"]
versions: ["Xcode 27.1 (27A9275)", "iOS Simulator 27.0 (24A434)", "iOS Simulator 18.6 (22G86, comparison)"]
tags: ["xcodebuild", "xcuitest", "simulator", "xcresult", "diagnostics", "sysdiagnose"]
project: "<sample-project>"
status: workaround
date: "2026-11-13"
---

## 现象

命令行 UI 测试已经输出全部通过，但 `xcodebuild` 继续运行，日志停在测试结束附近，迟迟没有最终成功标记和退出码。此时结果包还没有 `Info.plist`，导出附件报错：

```text
Failed to create a new result bundle reader
Info.plist at <result-bundle>/Info.plist does not exist
```

本次在 iPhone SE 3 / iOS Simulator 27.0 上出现：5 项 UI 测试全部通过后仍等待数分钟。iOS Simulator 18.6 的对照运行正常结束。上述现象不等于用例仍在执行，也不能单凭缺少 `Info.plist` 就判定结果包已经损坏。

## 原因

对仍在运行的 `xcodebuild` 采样，等待栈指向：

```text
XCTHRunDestinationAllocator.collectSimulatorDiagnostics
→ XCTHProcessInvocation.simCtlDiagnose
→ semaphore.wait
```

进程树中有属于该 `xcodebuild` 的专属子进程，完整命令包含：

```text
simctl diagnose ... --timeout=600 ...
  --output=<result-bundle>/Staging/...
  --udid=<test-simulator>
```

因此，本次已确认等待发生在测试执行后的模拟器诊断采集阶段，结果包尚未完成收尾。**为什么诊断采集迟迟未结束，以及为什么本轮用例全部通过后仍触发它，尚未隔离确认。** 同期出现的 `invalidDigitCount` 警告在后续成功运行中也存在，不能据此认定根因。

命令中的 600 秒是本次观察到的参数，不代表已验证它一定会在该时限内自动恢复；本次在超时前进行了精确干预。

## 解决方案

### 后续运行：按需关闭额外诊断采集

先用当前工具链的 `xcodebuild -help` 确认支持参数，再在本次命令中加入：

```sh
xcodebuild \
  -project SampleApp.xcodeproj \
  -scheme SampleAppUITests \
  -destination 'platform=iOS Simulator,id=REPLACE_WITH_UDID' \
  -resultBundlePath TestResults.xcresult \
  -collect-test-diagnostics never \
  test
```

项目、scheme 和目标标识均为示例，需要替换。该参数会减少失败时的系统诊断资料，不会关闭测试断言或显式添加的截图附件。本次后续 SE 补测、顶部布局复测及验收运行均使用此参数，正常完成并导出结果包；没有修改 Xcode 全局设置。需要调查系统级崩溃或挂起时，应保留所需诊断采集。

### 当前运行：先核实等待阶段，再决定是否干预

1. 保留日志，确认用例确实已经结束；用进程树和 `sample` 核对父进程的等待栈。
2. 核对诊断子进程的父 PID、完整命令、目标模拟器和输出结果包，确认它专属于这一次测试。
3. 可以继续等待诊断完成。若要提前结束诊断，只对已核实的专属 `simctl diagnose` 子进程发送 TERM，随后观察父 `xcodebuild` 是否能完成。不要先终止父进程，也不要使用泛化的 `pkill simctl`。
4. 不能只看测试通过行：还需检查父进程退出码、结果包 `Info.plist` 和正式导出是否成功。

本次精确结束诊断子进程后，父 `xcodebuild` 正常退出 **0**，日志出现 `TEST EXECUTE SUCCEEDED`，`Info.plist` 生成，附件可以正式导出。其他版本或不同等待原因未验证，不保证终止子进程后一定能完成归档。

### 结果包尚未收尾时：只读保全现成截图

优先保留原始结果包。其内部 `Data/data.*` 在本次已有 15 个以 PNG 文件头开头的完整文件，可以复制到另一目录，保持原包不动：

```python
from pathlib import Path
import shutil

bundle = Path("TestResults.xcresult")
output = Path("recovered-screenshots")
output.mkdir(parents=True, exist_ok=True)
png_header = b"\x89PNG\r\n\x1a\n"

for source in sorted((bundle / "Data").glob("data.*")):
    if not source.is_file():
        continue
    with source.open("rb") as stream:
        is_png = stream.read(8) == png_header
    if is_png:
        shutil.copy2(source, output / (source.name + ".png"))
```

这是本次存储形态下的应急保全方式，不是稳定公开的结果包解析接口，也不保证能恢复全部附件。原始文件名不等于截图的业务名称；按修改时间与日志顺序推测的映射需要人工确认，不能直接当作正式清单。

本次恢复出的 15 张 PNG 与后来正式导出的截图 SHA256 集合完全一致。正式结果包完成后，应改用工具导出和清单核对：

```sh
xcrun xcresulttool export attachments \
  --path TestResults.xcresult \
  --output-path exported-attachments
```

原始日志、诊断包和截图不随本文发布；这里只记录通用方法和经过确认的观察结果。

## 相关链接

- 本机命令帮助：`xcodebuild -help`、`xcrun xcresulttool export attachments --help`，参数以当前安装版本为准。
- [Apple：配置测试计划](https://developer.apple.com/documentation/xcode/organizing-tests-to-improve-feedback)：说明诊断采集、附件和屏幕捕获是分别配置的测试选项。
- [Apple：Xcode 16.3 Release Notes](https://developer.apple.com/documentation/xcode-release-notes/xcode-16_3-release-notes)：说明新版 `xcresulttool` 的附件导出与结果查询命令。这是工具命令参考，不是 Apple 对本次等待原因的确认。
