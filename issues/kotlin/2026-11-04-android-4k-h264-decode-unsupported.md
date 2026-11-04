---
title: "安卓设备解不了 4K H.264：ExoPlayer 只有 4K 素材报加载失败，其它分辨率正常"
stack: "kotlin"
platform: [android]
versions: ["media3 1.10.1", "android emulator API 37 (AOSP swcodec)"]
tags: [exoplayer, media3, mediacodec, h264, avc, 4k, decoder, video-resolution, android-tablet, transcode]
project: "tutuai"
status: open
date: "2026-11-04"
---

## 现象

安卓平板（真机，release 包）上，Media3 ExoPlayer 播 CDN 上的 MP4（progressive）。**某一个内容分类的视频全部播不了**，播放器回调 `onPlayerErrorChanged` 出错，页面显示「视频加载失败，请检查网络后重试」。同一台设备上其它分类的视频都正常。iPad 上同一批文件播放正常。

先排除过的方向（都不是原因）：

- 地址 / 网络：所有分类在同一个 CDN 域名下，响应头相同（`206`、`content-type: video/mp4`、支持 Range），文件能完整下载。
- 文件损坏：下载下来逐 box 解析，结构完整（ftyp → moov → mdat，faststart 过）。
- 接口：详情接口正常返回了播放地址，是播放器自己报的错。

## 原因

**失败的那个分类几乎全是 4K**，其它分类都在 1080p 以内。用 Range 请求只读每个文件的 moov，解析视频轨 `stsd` 里 `avc1` 的宽高和 `avcC` 的 profile / level，对全部内容做统计：

```text
失败分类（120 条）：119 条 avc1 3840x2160 High(100) L5.1，约 1 Mbps；1 条 1920x1080 Main L4.0
正常分类 A（124 条）：1920x1080 L4.0 ×88、1280x720 L3.1 ×36
正常分类 B（97 条）：1920x1080 / 1280x720 / 854x480 H.264，另有 7 条 HEVC 1080p
```

安卓对 4K H.264 解码没有硬性要求，设备能不能解要看芯片：

- CDD 对 H.264 解码的硬性要求只到 1080p，中低端平板的硬解普遍只支持到 1080p / 2K。
- 系统自带的软解也兜不住。AOSP 软解 `c2.android.avc.decoder`（`/apex/com.android.media.swcodec/etc/media_codecs.xml`）分两个变体：`!slow-cpu` 上限 4096×4096、block-count 34560；**`slow-cpu`（低配设备用）上限 2048×2048、block-count 16384**。4K 需要 3840/16 × 2160/16 = 32400 个宏块，超出这个上限。
- Media3 默认 `DefaultTrackSelector` 的 `exceedRendererCapabilitiesIfNecessary = true`：没有解码器声明支持时，照样选这条轨去解，结果在解码器初始化或解码阶段报错。所以表现为「加载失败」，不会提示格式不支持。

iPad 的芯片都能硬解 4K H.264，所以只在安卓上出问题。

**未核实的部分**：真机的具体 `errorCodeName` 没拿到（release 包不记日志）。预期是解码器类错误码，即 4001 `ERROR_CODE_DECODER_INIT_FAILED`、4003 `ERROR_CODE_DECODING_FAILED`、4004 `ERROR_CODE_DECODING_FORMAT_EXCEEDS_CAPABILITIES` 之一。模拟器用的是交给宿主机硬解的 `c2.goldfish.h264.decoder`，很可能能播 4K，复现不了。

## 解决方案

**根治在素材侧：转成 1080p。** 客户端绕不过去：没有别的解码器能解，就是解不了。

```bash
# 1080p H.264 High@4.0，音频原样拷贝，moov 挪到文件头（顺带让从中间位置起播更快）
ffmpeg -i in.mp4 -vf "scale=-2:1080" -c:v libx264 -profile:v high -level 4.0 \
  -preset slow -crf 23 -c:a copy -movflags +faststart out.mp4
```

- 上传入口要加限制（≤1080p），或者开云存储的自动转码，否则下次还会有人传 4K。剪辑软件默认导出 4K 的情况很常见。
- 平板全屏也只有约 2560 宽，内嵌播放区域更小，4K 在播放端没有收益。

**客户端能做的只有兜底，都治不了本：**

- `DefaultRenderersFactory(context).setEnableDecoderFallback(true)`：硬解初始化失败时换下一个解码器。在 `slow-cpu` 设备上软解同样不支持 4K，基本没用；能软解的设备上 4K 软解也会很卡。
- 失败提示区分错误码：`PlaybackException.errorCode` 在 4001–4005（解码器类）时提示「本设备暂不支持播放该视频」，不要统一写「请检查网络」。这条文案误导了排查。
- 播放前预检（可选）：`MediaCodecList(REGULAR_CODECS)` 遍历 `video/avc` 解码器，用 `capabilitiesForType("video/avc").videoCapabilities.isSizeSupported(3840, 2160)` 判断。

**排查方法（可复用）**：

- 不装 ffmpeg 也能统计一批线上视频的分辨率：只发 Range 请求读 moov（faststart 的文件在头 64KB 内；没 faststart 的沿顶层 box 往后跳到末尾），解析 `stsd/avc1` 的宽高（entry 偏移 32 处两个 uint16）和 `avcC` 的第 1、3 字节（profile_idc、level_idc）。HEVC 看 `hvc1` / `hev1`。
- 设备解码能力：`adb shell cat /vendor/etc/media_codecs*.xml /apex/com.android.media.swcodec/etc/media_codecs.xml`，看各 AVC 解码器的 `Limit name="size"` / `block-count`。
- 真机确认：拿同一分类里唯一一条 1080p 的内容在真机上点播，能播就坐实是分辨率问题。

## 相关链接

- Android CDD §5.3.4 H.264 解码要求：<https://source.android.com/docs/compatibility/cdd>
- Media3 `PlaybackException` 错误码：<https://developer.android.com/reference/androidx/media3/common/PlaybackException>
- 同批素材的另一个问题（moov 在末尾导致中间起播慢）：`kotlin/2026-10-12-exoplayer-mp4-slow-mid-position-start.md`
