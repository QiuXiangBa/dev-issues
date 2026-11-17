---
title: "DevEco 命令行 ohpm / hvigorw 只从 PATH 或 NODE_HOME 找 node，系统另装的 node 会掩盖配置缺失"
stack: "common"
platform: []
versions: ["DevEco Studio 26.0.0", "ohpm 26.0.0.630", "hvigor 6.26.9", "DevEco 自带 node v24.14.1", "macOS"]
tags: [harmonyos, deveco, ohpm, hvigor, nodejs, path, node-home, cli, build]
project: "<鸿蒙项目>"
status: solved
date: "2026-11-17"
---

## 现象

在 macOS 命令行（不经 DevEco Studio IDE）构建 HarmonyOS 工程，直接调用 DevEco 安装目录下的 ohpm 和 hvigorw。

如果 PATH 里没有任何 `node`，也没有设置 `NODE_HOME`，`ohpm install --all` 会以退出码 1 失败：

```
ERROR: node: .../DevEco-Studio.app/Contents/tools/ohpm/bin/ohpm: line 7: node: command not found
ERROR: NODE_HOME: .../ohpm: line 11: /node: No such file or directory
ERROR: Failed to find the executable 'node' command, please check the following possible causes:
       1. NodeJs is not installed.
       2. 'node' command not added to PATH;
       and the 'NODE_HOME' variable is not set in the environment variables to match your NodeJs installation location.
```

`hvigorw` 同样以退出码 1 失败：

```
ERROR: NODE_HOME is not set and not 'node' command found in your path
```

更隐蔽的情况是：**本机另外装了 node**（nvm、Homebrew、`~/.local/bin` 等）。这时同样的命令会成功，因为 ohpm 静默使用了 PATH 上的那个 node，而不是 DevEco 自带的。

本次就是这样。项目 README 把 `ohpm install` 写在 `export PATH=$DEVECO/tools/node/bin:$PATH` 之前。作者机器上另有一个 node（v24.20.0），全新克隆后按 README 验收也能通过。直到代码审查读了 ohpm 脚本才发现：在没有系统 node 的机器上照 README 执行，第一步就会失败。

## 原因

DevEco 自带了 node（`DevEco-Studio.app/Contents/tools/node/bin/node`），但 `tools/ohpm/bin/ohpm` 和 `tools/hvigor/bin/hvigorw` 都是 shell 包装脚本，**不会自动定位这份自带的 node**。两个脚本的查找顺序也不一样（读脚本源码确认）：

| 脚本 | 查找顺序 |
|---|---|
| `ohpm` | 先用 PATH 上的 `node`；不可用时再试 `$NODE_HOME/node`，然后 `$NODE_HOME/bin/node` |
| `hvigorw` | 设置了 `NODE_HOME` 就只用 `$NODE_HOME/bin/node`（目录无效直接报错）；没设置才找 PATH 上的 `node` |

IDE 内构建由 IDE 注入环境，不受影响，所以问题只出现在命令行、CI 或脚本里。

两个脚本都会使用环境里碰巧存在的 node，带来两个后果：

- 文档或脚本漏配环境变量的问题被掩盖，换到一台没有 node 的机器才暴露；
- 实际运行的 node 和 DevEco 自带版本不同，而且因为查找顺序不同，ohpm 和 hvigorw 甚至可能各用一个 node，出现版本相关问题时很难定位。

## 解决方案

在**第一条** ohpm / hvigorw 命令之前，同时设置 PATH 和 `NODE_HOME`，都指向 DevEco 自带的 node：

```bash
DEVECO=/Applications/DevEco-Studio.app/Contents
export PATH="$DEVECO/tools/node/bin:$PATH"   # ohpm 先查 PATH，必须放在最前
export NODE_HOME="$DEVECO/tools/node"         # hvigorw 先查 NODE_HOME；ohpm 也能识别这个目录
export DEVECO_SDK_HOME="$DEVECO/sdk"

"$DEVECO/tools/ohpm/bin/ohpm" install --all
"$DEVECO/tools/hvigor/bin/hvigorw" assembleHap --mode module \
  -p product=default -p module=entry@default -p buildMode=debug --no-daemon
```

要点：

- 只设 PATH：如果用户环境里已经有一个指向别处的 `NODE_HOME`，hvigorw 会用那个 node。
- 只设 `NODE_HOME`：如果 PATH 上已经有其他 node，ohpm 会用 PATH 上的那个。
- 两个都设，两边才都确定使用自带 node。README、CI 脚本里的 `export` 要写在所有 ohpm / hvigorw 命令之前，不能只写在构建命令那一段。

### 验证方法

用干净的环境按文档执行，才能确认文档本身完整，不依赖本机的偶然环境：

```bash
env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin bash -c '
  command -v node && echo "PATH 不干净" || echo "无系统 node"
  # 在这里逐行粘贴 README 的命令
'
```

本次修正顺序后，在上面这个干净 PATH 下全新克隆执行：`node` 解析为 DevEco 自带的 v24.14.1，`ohpm install --all`、hvigor 构建和宿主机测试均通过。当时项目 README 只加了 PATH，没有设 `NODE_HOME`；在干净环境里没有问题，但按上表，环境中预设了 `NODE_HOME` 时仍可能用错 node。

### 边界

- 只在 macOS + DevEco Studio 26.0.0 的命令行工具上验证过；Windows 的 `.bat` 包装和其他 DevEco 版本未验证。
- “两个都设”的写法依据脚本源码推导，没有逐一构造“环境里预设了另一个 `NODE_HOME`”的场景实测。
- 没有比较不同 node 版本对 ohpm / hvigor 行为的实际影响。“版本不一致难排查”是风险提示，不是已复现的问题。

## 相关链接

- 查找逻辑以本机脚本源码为准：`DevEco-Studio.app/Contents/tools/ohpm/bin/ohpm`、`DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw`（文件开头的 node 查找段）
- 同期 HarmonyOS 记录：[PixelMap 导出行距](2026-11-17-pixelmap-readback-packed-row-stride.md)、[XComponent 透明背景](2026-11-17-xcomponent-egl-transparent-background.md)
