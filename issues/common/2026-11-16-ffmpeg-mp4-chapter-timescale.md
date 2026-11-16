---
title: "FFmpeg 9 未显式指定 movie timescale 时 MP4 章节异常"
stack: "common"
platform: []
versions: ["FFmpeg 9.0", "libavformat 63.1.100", "PyAV 19.0.2"]
tags: ["ffmpeg", "mp4", "chapters", "timescale", "remux"]
project: "local-media-pipeline"
status: workaround
date: "2026-11-16"
---

## 现象

在 macOS Apple Silicon 上，将 H.264 30 fps 视频、AAC 48 kHz 音频、mov_text 字幕和含 6 段章节的 ffmetadata 封装为 MP4。未显式指定输出 `movie_timescale` 时，输入章节正确，成片前两章的时间和标题却错误。

封装日志出现：

```text
Application provided duration: 2254752000 in stream 3 is invalid
Packet duration: 2719824000 / dts: 2719824000 in stream 3 is out of range
```

导出的前两章时基为 `1/48000000`，第一章结束时间接近 0，第二章错误地使用末章标题。FFmpeg CLI 读取、导出 ffmetadata 和 PyAV 连续 3 次读取均得到相同结果，异常已存在于封装文件，不能只归因于 Python 读取接口。

## 原因

同一组视频、音频、字幕和章节元数据，仅改变输出 `movie_timescale` 的对照实验得到：

- 显式设为 `1000`，6 章的标题和毫秒时点全部正确。
- 只设 `video_track_timescale=30000` 不能修复。
- `movie_timescale=30` 或 `100` 可消除上述日志，但会量化章节时间。

据日志和数值推断，异常的大章节时基使部分 duration 超出有符号 32 位范围，导致章节封装异常。尚未分析 FFmpeg 内部调用栈，因此这是本次构建和输入组合下的原因推断，而不是所有 FFmpeg 版本的确定根因。

官方格式文档将 `movie_timescale` 定义为电影头 `mvhd` 的时基，并列出默认值 `1000`。本记录中的“未显式指定”仅描述实测命令，不据此断言所有构建的默认值或自动选择行为。

## 解决方案

封装时显式设置 `-movie_timescale 1000`，从原始正确的 ffmetadata 重建章节；不要沿用已损坏的章节数据。

下面示例从 `picture.mp4` 取视频，从包含音频和 mov_text 字幕的 `old.mp4` 取音频及字幕，从 `chapters.ffmeta` 取章节：

```sh
ffmpeg -i picture.mp4 -i old.mp4 -f ffmetadata -i chapters.ffmeta \
  -map 0:v:0 -map 1:a:0 -map 1:s:0 \
  -map_metadata 2 -map_chapters 2 -c copy \
  -movie_timescale 1000 -movflags +faststart output.mp4
```

若输入没有字幕，删除 `-map 1:s:0`。不要覆盖唯一源文件。

封装后重新读取输出章节，逐条对照预期标题与起止时点：

```sh
ffmpeg -i output.mp4 -f ffmetadata -
```

本次验证 6 章均恢复正确；同时逐包比对 AAC 的 payload、包数量、PTS、DTS、duration 和 codec extradata，全部与输入音轨一致，字幕文字和时间也一致。对已有声音的成片进行修复时，应保留这些校验，确认修章节没有改变音轨或字幕。

## 相关链接

- [FFmpeg Formats：MOV/MP4 muxer 选项](https://ffmpeg.org/ffmpeg-formats.html)：`movie_timescale` 与 `video_track_timescale` 的含义。文档用于解释参数，不作为上述实测异常根因已获上游确认的证据。
