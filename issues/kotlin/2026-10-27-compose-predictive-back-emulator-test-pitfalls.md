---
title: "模拟器测 Compose NavHost predictive back：动画时长放大后预览不动、慢速注入手势被系统取消"
stack: "kotlin"
platform: [android]
versions: ["navigation-compose 2.9.1", "compose-bom 2025.06.00", "kotlin 2.1.20", "agp 8.11.1", "android emulator api 37 (android 17)"]
tags: [compose, navigation-compose, predictive-back, animator-duration-scale, emulator, adb, input-swipe, walkthrough]
project: "xuejieai"
status: solved
date: "2026-10-27"
---

## 现象

给 Navigation Compose 的 `NavHost` 配了 push 转场（`enterTransition` 右滑入、`popExitTransition` 右滑出）后，在模拟器上验证 predictive back（targetSdk 36、Android 16+ 默认开）的页内跟手预览，用 `adb` 注入左缘侧滑：

```bash
adb shell settings put global animator_duration_scale 10   # 之前为了截转场中段帧放大的
adb shell input swipe 5 1400 900 1400 8000 &                # 8 秒慢速侧滑
adb exec-out screencap -p > frame.png                        # 手势中途截帧
```

两个症状：

1. **手势进行中页面几乎不动**：手指走了 590px，页面只右移 8px；松手后才按普通 pop 动画滑出。logcat 里 `CoreBackPreview: startBackNavigation ... mIsAnimationCallback=true` 说明 App 的动画回调确实在接管，容易误判成转场配置没生效。
2. **部分注入手势根本没触发返回**：同样的 `input swipe`，有的页面 4/4 成功、有的页面 1/3，失败时 logcat：

```
ShellBackPreview: Finishing gesture with event action: 3      # ACTION_CANCEL，手势开始后约 240ms
ShellBackPreview: Skipping dispatching onBackCancelled. Start was never dispatched.
CoreBackPreview: onBackNavigationDone backType=4, triggerBack=false
```

## 原因

1. `animator_duration_scale` 对 Compose 动画同样生效（`MotionDurationScale`），`tween(300)` 变成 3s；而 NavHost 的 predictive back 是用 `SeekableTransitionState.seekTo(progress)` 按手势进度定位同一条 `popExitTransition`。时长被放大 10 倍后，同一个进度值对应的动画位置被压到原来的 1/10 附近，再叠上 `tween` 默认的 FastOutSlowIn 缓动（起步段位移极小），结果就是「手指走很远页面不动」。恢复 1x 后 385px 行程对应 252px 位移，正常跟手。
2. 慢速匀速的 `input swipe`（约 110px/s）在系统 SystemUI 的边缘返回手势判定里容易在起步阶段被判为无效手势而取消（取消发生在 start 派发给 App 之前），与 App 代码无关；换成接近真人速度（约 600ms 走 700px）后 3/3 触发。

## 解决方案

- **截时间驱动的转场中段帧**（push / pop / cover 动画）可以用 `animator_duration_scale = 10`，tap 后约 1.2s 截帧；**测 predictive back 跟手必须用 1x**，两种走查分开做，走完改回：

```bash
adb shell settings put global animator_duration_scale 1
adb shell settings get global animator_duration_scale
```

- 量手势跟手位移：1x 下用 8s 慢速侧滑放后台，循环 `screencap`（每帧约 1.1s），再把每帧与静止帧按横向对齐算 shift（纯 Python 解 PNG 即可，不需要 PIL）。正常数据参考：手指行程 210px → 位移 15px，385px → 252px，570px → 已基本滑出。
- 只验证「手势能否触发返回」用真人速度：`adb shell input swipe 5 2000 700 2000 600`，看 logcat `onBackNavigationDone ... triggerBack=true`。
- 判断 App 是否在接管手势看 logcat：`adb logcat -d | grep -i 'CoreBackPreview\|ShellBackPreview'`，`mType=TYPE_CALLBACK` + `mIsAnimationCallback=true` 即 `PredictiveBackHandler` 已注册；只有 `mIsAnimationCallback=false, mPriority=-1` 说明当前没有启用的 BackHandler（栈底或未开 `enableOnBackInvokedCallback`）。
- 顺带：`enableOnBackInvokedCallback` 的「默认开」只在 targetSdk 36 且运行在 Android 16+ 时成立，13–15 设备要在 Manifest 显式开才跟手。

## 相关链接

- NavHost 的 predictive back 复用 popEnter / popExit 槽（2.9.x），新版本另有 `predictivePopEnterTransition` / `predictivePopExitTransition` 槽：https://developer.android.com/jetpack/androidx/releases/navigation
- Android 16 行为变更（predictive back 默认开）：https://developer.android.com/about/versions/16/behavior-changes-16#predictive-back
