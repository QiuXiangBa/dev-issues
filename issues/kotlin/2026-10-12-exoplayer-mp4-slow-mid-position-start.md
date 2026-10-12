---
title: "ExoPlayer 播放 MP4 从中间位置起播很慢：moov 在文件末尾 + 音视频错位存放导致反复重连"
stack: "kotlin"
platform: [android]
versions: ["media3 1.10.1", "okhttp 4.12.0", "android emulator API 37 (goldfish)"]
tags: [exoplayer, media3, mp4, moov, faststart, seek, resume, progressive, range-request, cdn]
project: "tutuai"
status: open
date: "2026-10-12"
---

## 现象

Media3 ExoPlayer 直接播 CDN 上的 MP4（progressive，不是 HLS / DASH）。从头播约 1 秒出画面；从中间位置续播（`seekTo(pos)` 后 `prepare()`），或进页面就带着续播位置，要 **8–10 秒**才出第一帧，之后播放流畅。没有报错。同一批文件 iOS AVPlayer 在同样位置约 1 秒起播。

这批文件的特征：720p / 1080p，码率 8–9 Mbps（5 分钟约 300MB），看起来像剪辑软件直接导出的原文件。

先排除过的方向（都不是原因）：

- 解码慢：模拟器用的是 `c2.goldfish.h264.decoder`（交给宿主机硬解）。
- 关键帧太稀 / 不是 IDR：`stss` 显示约 1 秒一个关键帧，抽查都是 NAL type 5（IDR）。
- 精确 seek 要从关键帧解码到目标位置：改成 `SeekParameters.PREVIOUS_SYNC`，起播点确实挪到了关键帧，但起播时间没有变化。

## 原因

给 `DefaultDataSource.Factory(...).setTransferListener(...)` 挂一个记录传输的 TransferListener，再加上 `EventLogger`，就能看到下载层实际在做什么（续播 308s，文件 446MB）：

```text
+1.5s  http start pos=0.00MB   → 读到 ftyp / mdat 头，没有 moov
+2.7s  http start pos=446.26MB → 读末尾的 moov（0.27MB），拿到时长
+4.5s  http start pos=311.35MB → 只读 0.01MB 就断开
+6.5s  http start pos=311.85MB → 只读 0.01MB 就断开
+8.2s  http start pos=312.35MB → 只读 0.01MB 就断开
+9.3s  http start pos=312.82MB → renderedFirstFrame，之后连续下载约 5MB/s
```

三个因素叠在一起：

1. **moov 在文件末尾**（没做 faststart）：先读开头，再跳到末尾读 moov，多一次请求。
2. **音视频错位存放**：chunk 本身是约 0.5 秒交替排的，但同一时刻的音频样本比视频样本靠前 1.5–5MB，而且越往后差得越多。从中间开始播时，两个位置之间夹着的是目标时间之前、用不到的视频 chunk（每块约 0.5MB）。
3. **Mp4Extractor 遇到超过 256KB 的用不到的数据不读，而是 reposition**（重新发一个 Range 请求跳过去）。于是变成「读一小块音频 → 断开 → 新请求」反复几次。`DefaultHttpDataSource` 在响应体中途断开后连接不能复用，每次都要重新握手。模拟器上一次新的 HTTPS 连接要 1.5–2 秒（电脑直连同一 CDN 约 0.1 秒），跳三四次就是好几秒。

从头播时音视频挨在一起、moov 之后顺序读，所以快。AVPlayer 的取数方式不同，不受这种布局影响。

## 解决方案

**根治（服务端，推荐）**：重新封装文件，不需要重新编码：

```bash
ffmpeg -i in.mp4 -c copy -movflags +faststart out.mp4
```

这会把 moov 挪到文件开头，muxer 也会按时间重新交织音视频，续播只需要一次 Range 请求。最好同时转码到正常码率（720p 约 2–3 Mbps，关键帧间隔约 2 秒），或者直接转成 HLS / DASH，续播只拉续播点所在的那一片。

**客户端缓解（有坑，未采用）**：改用 OkHttp 数据源，走 HTTP/2 复用连接，中途断开只取消单个 stream、不断连接：

```kotlin
// build.gradle: implementation("androidx.media3:media3-datasource-okhttp:<media3 版本>")
ExoPlayer.Builder(context)
    .setMediaSourceFactory(DefaultMediaSourceFactory(
        DefaultDataSource.Factory(context, OkHttpDataSource.Factory(okHttpClient))))
    .build()
```

实测读 moov 从 2.7s 降到 0.46s。但这次的 CDN（腾讯云，`server: tencent-cos`）对随后快速连续的 Range 请求返回了 **514 / 416**，播放直接失败。用这条路前，要先确认 CDN 的频率限制和 Range 配置，并处理好重试。

**诊断方法**（不依赖播放器内部，只发 Range 请求）：

- 读顶层 box 的顺序，看 moov 在 mdat 前还是后。
- 解析视频轨的 `stss` / `stts`，看关键帧间隔。
- 解析两条轨的 `stsz` / `stco` / `stsc`，算出同一时刻视频样本和音频样本的字节偏移差。差值超过约 256KB，从这里起播就会被 reposition 拖慢。

**说明**：服务端重新封装之后的效果这次还没验证（文件不归客户端管）。验证后用 update 把 status 改为 solved。真机上建连接一般 0.1–0.3 秒，这个问题会轻很多，但文件布局的问题依然存在。

## 相关链接

- ffmpeg mov / mp4 muxer 的 `-movflags faststart`：https://ffmpeg.org/ffmpeg-formats.html（mov, mp4, ismv 一节）
- Media3 OkHttp 数据源：https://developer.android.com/media/media3/exoplayer/network-stacks
- Mp4Extractor（`RELOAD_MINIMUM_SEEK_DISTANCE` = 256KB）：https://github.com/androidx/media/blob/release/libraries/extractor/src/main/java/androidx/media3/extractor/mp4/Mp4Extractor.java
