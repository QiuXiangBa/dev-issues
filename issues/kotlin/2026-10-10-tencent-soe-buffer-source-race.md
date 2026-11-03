---
title: "腾讯智聆口语评测 Android SDK 自定义数据源回放整段 PCM 时与建连竞态，音频被静默丢弃导致超时"
stack: "kotlin"
platform: [android]
versions: ["qcloud-soe-android 2.0.10"]
tags: [tencent-cloud, soe, speech-evaluation, websocket, okhttp, race-condition, audio, timeout, rate-limit, streaming]
project: "kakaai"
status: solved
date: "2026-10-10"
---

## 现象

腾讯云「智聆口语评测（新版）」Android SDK v2.0.10，实时评测模式（`TAIOralController.startOralEvaluation`）。数据源没用 SDK 自带录音，而是自定义 `TAIPcmDataSource`，把**已经录完的整段 16k PCM** 回放给 SDK（「按住说话、松手送评」的交互）。

时好时坏：约一半请求既不回调 `onFinish` 也不回调 `onError`，一直挂到业务层超时（15s）主动取消，SDK 才回调 `onError(ClientException -107 "Oral evaluation is cancelled")`。全程没有任何警告 / 错误日志。

失败时的 logcat（debug 包，`AAILogger` 全开）：

```
I/OralEvaluationer: pcmAudioDataSource read Length = -1
I/OralEvaluationer: handle on finish.
D/WebsocketHelper: send end
D/WebsocketHelper: prepare send websocket connect.wss://soe.cloud.tencent.com/soe/api/<appId>?…
D/WebsocketHelper: onOpen
D/WebsocketHelper: WebSocketListener onMessage String{"code":0,"message":"success",…,"final":0}
（之后再无消息，直到超时取消）
```

成功的请求里，`prepare send websocket connect` 出现在 `send end` **之前**。

## 原因

SDK 建 WebSocket（`WebsocketHelper`）和读数据源（`OralEvaluationer$OralEvaluationRunnable`）在两个线程里并行：

- 自定义数据源回放内存里的整段 PCM，几毫秒就读完、返回 -1，SDK 立刻发结束帧 `{"type": "end"}`。
- 反编译 v2.0.10：`WebsocketHelper.sendMessage(AudioMessage)` / `sendEnd()` 开头就是 `if (mSocket == null) return;`。连接对象还没由 `OkHttpClient.newWebSocket()` 创建时，音频帧和结束帧**直接丢弃，不打日志、不回调错误**。
- 如果连接对象先创建，OkHttp 会把发送排进队列、等 `onOpen` 后发出，所以有时正常。
- 服务端握手成功后一直等音频，等不到就挂住。
- 用 SDK 自带的麦克风数据源时，数据按实时速度产生，连接总是先建好，问题不会暴露；只有「回放已录好的音频」才会撞上。

验证：模拟器 10 次中 5 次超时，逐次核对 logcat，5 次超时全是「`send end` 先于 `prepare send websocket connect`」，5 次成功全是相反顺序。

## 解决方案

数据源在**服务端握手成功前 `read()` 返回 0**，`TAIListener.onMessage` 收到首帧（握手 `success`，此时连接已建立）后再放行。反编译确认 SDK 读到 0 会 `Thread.sleep(10)` 后重读、不发任何东西，读到 -1 才收尾；SDK 只把 `code == 0` 的非终帧回调到 `onMessage`。这也符合实时评测协议「握手成功后再发音频」的顺序。修复后模拟器 25/25 出分，出分耗时不变。

```kotlin
class PcmBufferSource(pcm: ByteArray) : TAIPcmDataSource {
    private val samples: ShortArray = ShortArray(pcm.size / 2).also {
        ByteBuffer.wrap(pcm, 0, it.size * 2).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(it)
    }
    private var cursor = 0

    @Volatile
    private var opened = false

    /** 服务端握手成功后调用（幂等）。 */
    fun open() {
        opened = true
    }

    override fun read(audioPcmData: ShortArray, length: Int): Int {
        if (!opened) return 0                 // 握手前不给数据：SDK sleep 10ms 后重读
        val remaining = samples.size - cursor
        if (remaining <= 0) return -1         // 读完：SDK 发结束帧
        val count = minOf(length, remaining, audioPcmData.size)
        System.arraycopy(samples, cursor, audioPcmData, 0, count)
        cursor += count
        return count
    }

    override fun start() = Unit
    override fun stop() = Unit
    override fun isCallbackAudioData(): Boolean = false
}

val source = PcmBufferSource(pcm)
val config = TAIConfig.Builder()
    // … appID / secretID / secretKey / apiParams …
    .enableVAD(false)
    .dataSource(source)
    .build()
TAIOralController(config).startOralEvaluation(object : TAIListener {
    override fun onMessage(msg: String) = source.open()   // 首帧即握手成功
    // onFinish / onError / onVad / onVolumeDb …
}, stateListener)
```

排查方法：debug 包里看 `prepare send websocket connect` 和 `send end` 谁先出现即可判定。

### 同一 SDK（v2.0.10）的其它坑

- **`ServerException` 不公开错误码**：`code` 是 private 且没有 getter，只有 `toString()`。服务端错误码从 `onError` 的 `response` 参数取，它就是服务端原始 JSON，读顶层 `code`。
- **终帧出错走 `onFinish`，不走 `onError`**：`final:1` 的帧不管 `code` 是不是 0 都回调 `onFinish`，要自己判 `code`；只有非终帧 `code != 0` 才走 `onError(…, ServerException, response)`。
- **发布包日志**：`AAILogger` 默认四级全开，debug / info 会把带签名的 WebSocket URL 打进 logcat，发布包应调 `AAILogger.disableDebug()` / `disableInfo()`。warn / error 仍会输出，排查发布包可用 `adb logcat '*:W'`。
- **别用录音评测模式**（`REC_MODE=1` + `recordAudioData`）：`RecordFileOralEvaluationTask.run()` 是没有 sleep 的 `while (!isExit)`，握手失败或开连接前被取消时线程永久空转，`release()` 停不掉，每次重试再泄漏一条。

## 相关链接

- SDK 为腾讯云控制台下载的 AAR（`qcloud-soe-release-v2.0.10`），无公开源码，以上行为均为反编译确认
- 项目内记录：私有仓库 Issue #720 / PR #721

## 更新 2026-11-03

上面的解法（整段回放 + 握手闸）还有第二个坑：**录音超过约 8 秒，服务端回终帧报 4000**，原文 `{"code":4000,"message":"音频数据发送过多，请1秒内最多发送3秒音频数据","final":0}`，随后断开连接。只有长句才会触发，单词、短句测不出来，与机型无关。

### 原因

- 反编译 v2.0.10 的 `OralEvaluationer$OralEvaluationRunnable.run()`：`read()` 读到数据（> 0）就立刻发出，马上读下一帧；只有返回 0 才 `Thread.sleep(10)`。**SDK 自己不限速**，发送节奏完全靠数据源 `read()` 阻塞。默认数据源 `AudioRecord.read()` 天然按实时节奏返回，自定义数据源则不会。
- 回放内存里的整段 PCM 时，握手一放行，整段约 10ms 内全部发完。
- 官方文档（[1774/107497](https://cloud.tencent.com/document/product/1774/107497)）建议每 40ms 发 40ms 音频（16k PCM 为 1280 字节），即 1:1 实时率；4000 的含义是「1 秒内最多发送 3 秒音频」。服务端对突发有一定容忍，直连实测一次性发送：5.5 / 7.3 / 8.0s 正常出分，9.0 / 9.5 / 11 / 14.5s 全部报 4000。

### 解决方案：边录边送（推荐）

按下就 `startOralEvaluation`，数据源改成流式缓冲：

- 录音线程每采一块就 `append` 一块；
- `read()` 读空时返回 0，SDK 会 sleep 10ms 再读；
- 松手时调 `end()`，之后读空才返回 -1，SDK 据此发结束帧；
- 握手闸照旧保留：握手前 `read()` 一律返回 0，握手期间攒下的录音放行后一次补发（常态 0.2–1.5s，远低于突发上限）。

这样发送速率天然是 1:1，服务端边收边评，松手后几百毫秒内就出分（原来要等整段发完、评完）。真机实测：12s 录音得 96 分，20s 录音得 97 分。

```kotlin
class PcmStreamSource : TAIPcmDataSource {
    private val lock = Any()
    private var samples = ShortArray(16_000)
    private var size = 0
    private var cursor = 0
    private var ended = false
    @Volatile private var opened = false

    fun open() { opened = true }                       // TAIListener.onMessage 首帧（握手成功）时调用

    fun append(pcm: ByteArray, length: Int) {          // 录音线程逐块调用（s16le）
        val count = length / 2
        synchronized(lock) {
            if (ended) return
            if (size + count > samples.size) samples = samples.copyOf(maxOf(samples.size * 2, size + count))
            ByteBuffer.wrap(pcm, 0, count * 2).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(samples, size, count)
            size += count
        }
    }

    fun end() { synchronized(lock) { ended = true } }  // 松手

    override fun read(audioPcmData: ShortArray, length: Int): Int {
        if (!opened) return 0
        synchronized(lock) {
            val remaining = size - cursor
            if (remaining <= 0) return if (ended) -1 else 0
            val count = minOf(length, remaining, audioPcmData.size)
            System.arraycopy(samples, cursor, audioPcmData, 0, count)
            cursor += count
            if (cursor == size) { cursor = 0; size = 0 }  // 读空即复位，缓冲只需装下握手期间的积压
            return count
        }
    }

    override fun start() = Unit
    override fun stop() = Unit
    override fun isCallbackAudioData(): Boolean = false
}
```

收尾时的注意点：

- 结果用 `CompletableDeferred` 收口，只认第一次完成（`cancelOralEvaluation()` 会在锁内同步回调 `onError(-107)`）。录音中途出错先存进去，松手时再抛出。
- `startOralEvaluation` 同步抛异常时，SDK 读线程已经起来了，要 `cancelOralEvaluation()` + `release()`，否则读线程每 10ms 读一次 0，一直空转。

### 替代方案

- **必须回放已录好的音频时**：在 `read()` 里按「已发样本数 ≤ 放行后经过时间 × 2 倍实时」限量返回。代价是出分要多等约一半的录音时长。
- **服务端的录音识别模式（`rec_mode=1`）**：允许整段一次性发送（上限 60s），直连实测 14.5s 录音 2s 出分。但 SDK 设了 `REC_MODE=1` 会改走 `RecordFileOralEvaluationTask`，有上文说的线程空转问题，只适合不经过 SDK、自己直连服务端的场景。

### 排查手段：绕过 SDK 直连服务端

Node 24 自带 `WebSocket`，几十行就能复现服务端行为（限速阈值、模式差异）：

- 地址为 `wss://soe.cloud.tencent.com/soe/api/<appId>?<参数>&signature=<sig>`。参数包括：
  - `secretid`、`timestamp`、`expired`、`nonce`、`voice_id`
  - `server_engine_type=16k_en`、`voice_format=0`、`text_mode=0`
  - `ref_text`、`eval_mode`、`score_coeff`、`sentence_info_enabled`，可选 `rec_mode`
- 签名为 `base64(HMAC-SHA1(secretKey, "soe.cloud.tencent.com/soe/api/<appId>?" + 按 key 排序的 k=v 用 & 连接（值不编码）))`；URL 里每个值和签名都要 `encodeURIComponent`。
- 收到握手 `code:0` 后发二进制 PCM 帧，最后发文本 `{"type": "end"}`，等 `final:1`。
- 测试语音可用 macOS `say -v Samantha --file-format=WAVE --data-format=LEI16@16000 -o x.wav "..."` 生成。凭证从本地配置读取，不要打印出来。

项目内记录：私有仓库 Issue #735 / PR #736。
