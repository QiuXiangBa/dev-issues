---
title: "AVPlayer seek 到未缓冲处期间周期时间观察者继续报旧位置，自绘进度条退回再跳"
stack: "swift"
platform: [ios]
versions: [xcode 27, ios 18.6 simulator, macos 26]
tags: [avplayer, avfoundation, seek, periodic-time-observer, progress-bar, swiftui]
project: "tutuai"
status: solved
date: "2026-10-16"
---

## 现象

自绘播放器（`AVPlayer` + `AVPlayerLayer`，进度条用 `addPeriodicTimeObserver` 驱动）：播放中把进度条拖到**还没缓冲**的位置松手，滑块先退回拖之前的位置、慢慢往前爬约 1 秒（弱网下几秒），等 seek 落地再跳到目标。拖到已缓冲的位置不跳。连点两次「快进 10s」时第二下会从退回去的旧位置算起。

松手后的调用路径是 `elapsedSeconds = target` → `player.seek(to:toleranceBefore:.zero,toleranceAfter:.zero)`，时间观察者每 0.25s 把 `time.seconds` 写回 `elapsedSeconds`。

## 原因

`AVPlayer.seek(to:)` 到未缓冲处是**异步**的，落地前播放器继续播旧缓冲段。这期间：

- `addPeriodicTimeObserver` 回调的 `time` 参数是**旧位置，并且还在往前走**；
- `player.currentTime()` 在 seek 发出后几毫秒就已经是目标值；
- 落地时（`AVPlayerItem.timeJumpedNotification`）观察者才报目标值。

用独立脚本（macOS，本机限速 HTTP 服务 100 KB/s 喂一个 3 分钟视频）实测：播放中从 2.37s seek 到未缓冲的 9.07s，seek 挂起约 0.7s，观察者依次报 2.50 / 2.75 / 3.00 / 3.01，然后跳 9.07；`currentTime()` 从第一次回调起就是 9.07。seek 到已缓冲处也会有一次旧值回调，但 40ms 内纠正，肉眼看不见。零容差精确 seek 要从前一个关键帧解码到目标帧，把挂起窗口拉长，但不是根因。

ExoPlayer（安卓）没有这个问题：`currentPosition` 在 `seekTo` 后立刻返回目标位置，`onPositionDiscontinuity` 也立即回调。

## 解决方案

主流做法（系统 `AVPlayerViewController`、各开源播放器同款）：seek 挂起期间不让时间观察者回写进度，滑块钉在松手位置。用「seek 代数 + 标记」处理连续拖动：

```swift
private var isSeeking = false
/// 每次 seek / 换 item 自增；落地回调只认最后一次
private var seekGeneration = 0

timeObserver = player.addPeriodicTimeObserver(forInterval: CMTime(seconds: 0.25, preferredTimescale: 600), queue: .main) { [weak self] time in
    Task { @MainActor in
        guard let self, self.player.currentItem?.status == .readyToPlay, !self.isSeeking else { return }
        self.elapsedSeconds = max(time.seconds, 0)
    }
}

func seek(toFraction fraction: Double) {
    guard durationSeconds > 0 else { return }
    let target = min(max(fraction, 0), 1) * durationSeconds
    elapsedSeconds = target                 // 滑块 / 时间文案立刻钉在目标
    seekGeneration += 1
    let generation = seekGeneration         // 在调 seek 之前取：同步回调也对得上
    isSeeking = true
    // 有意不看 finished：被换 item / 播完重播 / 循环回头打断时播放器已不再奔向目标，该让观察者恢复回写；
    // 加 guard finished 会把标记卡住
    player.seek(to: CMTime(seconds: target, preferredTimescale: 600),
                toleranceBefore: .zero, toleranceAfter: .zero) { [weak self] _ in
        Task { @MainActor in
            guard let self, self.seekGeneration == generation else { return }
            self.isSeeking = false
        }
    }
}

// 失败后 replaceCurrentItem 换新 item 时：旧 item 上挂起的 seek 作废，别让观察者一直停更
seekGeneration += 1
isSeeking = false
```

要点：

- 连续拖动：新 seek 先把代数 +1，旧 seek 的回调以 `finished == false` 返回时代数已对不上，自然忽略；最后一次落地才清标记。
- 不要改成 `guard finished`：被 `replaceCurrentItem` / `seek(to: .zero)` 打断时 `finished == false` 且代数匹配，这正是该恢复观察者的时候。
- 不要放宽容差来「加快落地」：落点会偏到附近关键帧，滑块又会小挪一下。
- 代价：挂起期间画面 / 声音还在播旧段而滑块已在目标，主流播放器用画面上的缓冲转圈（`timeControlStatus == .waitingToPlayAtSpecifiedRate`）补这个反馈。

验证法：现象依赖异步 seek 时序，单测造不出。用本机限速（约 100 KB/s）+ 支持 Range 的 HTTP 服务喂一个带大号时间码的长视频，定时调 `seek(toFraction:)`，每 100ms 记一条 `elapsedSeconds`，修前 / 修后同一脚本对照；录屏按 0.25s 抽帧裁进度条拼图看滑块。

## 相关链接

- 项目内：QiuXiangBa/tutuai-app#431（分析）、PR #432（修复）、#433（缓冲中视觉反馈，待做）
- Apple 文档：[seek(to:toleranceBefore:toleranceAfter:completionHandler:)](https://developer.apple.com/documentation/avfoundation/avplayer/seek(to:tolerancebefore:toleranceafter:completionhandler:)) 、[addPeriodicTimeObserver(forInterval:queue:using:)](https://developer.apple.com/documentation/avfoundation/avplayer/addperiodictimeobserver(forinterval:queue:using:))
