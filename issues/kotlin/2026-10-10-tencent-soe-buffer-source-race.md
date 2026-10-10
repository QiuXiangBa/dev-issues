---
title: "腾讯智聆口语评测 Android SDK 自定义数据源回放整段 PCM 时与建连竞态，音频被静默丢弃导致超时"
stack: "kotlin"
platform: [android]
versions: ["qcloud-soe-android 2.0.10"]
tags: [tencent-cloud, soe, speech-evaluation, websocket, okhttp, race-condition, audio, timeout]
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
