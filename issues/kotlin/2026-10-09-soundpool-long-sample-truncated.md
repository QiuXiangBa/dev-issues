---
title: "Android SoundPool 播长音效被截掉结尾（单段解码上限约 1MB）"
stack: "kotlin"
platform: [android]
versions: [compileSdk 36, minSdk 24, kotlin 2.1.20, android 17 emulator]
tags: [android, soundpool, mediaplayer, audio, sound-effect, truncation]
project: "tutuai"
status: solved
date: "2026-10-09"
---

## 现象

给 App 加本地音效（res/raw 下的 mp3）：按钮点击 0.3 秒、答对 1.2 秒、通关 3.2 秒、当天完成 6.7 秒，都是 44.1kHz 立体声。按钮音、对错音这类短音效适合用 `SoundPool`（预先解码、延迟低、连点每下都响），但 6.7 秒那段放进 `SoundPool` 会被截掉结尾，而且不报错。

本项目是动手前按尺寸算出来、直接规避的，没有实际去复现截尾。

## 原因

`SoundPool` 把每段音效整段解码成 PCM，放进一块固定大小的共享内存里播放。这块内存默认约 1MB（AOSP `SoundPool` 原生层 `Sample` 的默认堆大小），解码出来超过的部分直接丢掉。

解码后的大小 = 时长 × 采样率 × 声道数 × 2 字节（16bit）：

- 6.71s × 44100 × 2 × 2 ≈ 1.18MB → 超限，44.1kHz 立体声大约 5.9 秒之后被截掉
- 3.19s × 44100 × 2 × 2 ≈ 0.56MB → 没问题

## 解决方案

按用途分开：

- 按钮 / 对错这类短提示音走 `SoundPool`。
- 通关、庆祝这类长音效走 `MediaPlayer`，播完释放。

```kotlin
// 短音效：SoundPool。先设加载监听再 load（见下方「附」）
val pool = SoundPool.Builder().setMaxStreams(4).setAudioAttributes(attributes).build()
val pending = mutableMapOf<Int, SoundEffect>()
pool.setOnLoadCompleteListener { _, id, status -> if (status == 0) pending[id]?.let { loaded[it] = id } }
SoundEffect.entries.filterNot { it.isLong }.forEach { pending[pool.load(context, it.res, 1)] = it }

// 长音效：MediaPlayer，再次播放先释放上一个，播完自己释放
celebration?.release()
celebration = MediaPlayer.create(context, res, attributes, AudioManager.AUDIO_SESSION_ID_GENERATE)?.apply {
    setOnCompletionListener { player ->
        player.release()
        if (celebration === player) celebration = null
    }
    start()
}
```

也可以把长音效转成单声道 / 22.05kHz 压到 1MB 以内，但这会改动素材音质，需要设计确认。

### 附：SoundPool 另外两个容易踩的点

- **先设 `setOnLoadCompleteListener` 再 `load()`。** `SoundPool` 只在已经设了监听时才投递加载完成事件。先 load 后设监听的话，解码快的那段可能在监听设上之前就完成了，事件被丢掉，这个进程里它就一直「没加载完」、不出声。这一条依据的是 `SoundPool` 源码和代码评审，本项目没有单独复现。
- **`stop()` 要传 `play()` 返回的流 id，不是 `load()` 返回的声音 id。** 要整体停掉就记下最近几条流 id（不超过 maxStreams 条，更早的已经被 SoundPool 顶掉了）。

## 相关链接

- https://developer.android.com/reference/android/media/SoundPool
- AOSP：frameworks/base/media/jni/soundpool/Sample.cpp（默认堆大小）
