---
title: "OkHttp WebSocket 服务端先关连接时只回调 onClosing，只在 onClosed 里收尾会一直挂到超时"
stack: "kotlin"
platform: [android, backend]
versions: ["okhttp 4.12.0"]
tags: [okhttp, websocket, close-frame, callback, timeout, hang]
project: "tutuai"
status: solved
date: "2026-10-10"
---

## 现象

OkHttp 4.12.0 客户端 WebSocket（一次请求一条连接：发完数据，等服务端回最终结果）。监听器在 `onClosed` 里处理「服务端没给结果就关了连接」；拿到结果后收尾只调 `webSocket.cancel()`，从不调 `close()`。

服务端发来关闭帧（如 1000）后，客户端只收到 `onClosing`，之后既没有 `onClosed`，也没有 `onFailure`，调用方一直挂到自己设的超时。全程没有异常和日志。

复现：用 MockWebServer，服务端收到客户端的结束消息后直接 `close(1000, ...)`，不给结果。

```
   60ms onClosing 1000
 8032ms （业务超时；这期间再没有任何回调）
```

对照：在 `onClosing` 里回一个 `close(1000, null)`，`onClosed` 立刻就到：

```
   52ms onClosing 1000
   52ms onClosed 1000
```

## 原因

以下行为用 javap 反汇编 OkHttp 4.12.0 的 `RealWebSocket.onReadClose` 确认：

- 收到对方的关闭帧时，先记下关闭码。只有本端已经调过 `close()`（`enqueuedClose`）且发送队列已空，才会在 `onClosing` 之后紧接着调 `onClosed` 并释放连接。
- 否则只调 `onClosing`，等应用自己调 `close()` 回关闭帧；写线程把关闭帧发出去之后才回调 `onClosed`。
- 读循环收到关闭帧就退出、不再读，所以对方随后断开 TCP 也不会触发 `onFailure`。

`onClosing` 的意思是「对方不会再发消息了」，`onClosed` 是「双方都关了、连接已释放」。收尾只用 `cancel()` 的代码，对方先关时永远等不到 `onClosed`。

## 解决方案

「对方关了连接」的处理要写在 `onClosing` 里，二选一：

1. **只关心结果，不在乎完成关闭握手**：在 `onClosing` 里直接收尾并 `cancel()`。本例用的就是这个。
2. **要按协议完成关闭握手**：在 `onClosing` 里调 `webSocket.close(code, null)`，收尾仍放在 `onClosed`。

```kotlin
val socket = client.newWebSocket(request, object : WebSocketListener() {
    override fun onMessage(webSocket: WebSocket, text: String) {
        // 拿到最终结果 → finish(webSocket, result)
    }

    override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) = finish(webSocket, null)

    // 对方先关：OkHttp 只回调这里；onClosed 要等本端也 close() 过才来
    override fun onClosing(webSocket: WebSocket, code: Int, reason: String) = finish(webSocket, lastPartialResult)
})

// finish：用 AtomicBoolean 保证只交回一次，再 socket.cancel()；cancel 之后可能还会来一次 onFailure，由这个开关挡掉
```

回归测试写法：MockWebServer 的 `withWebSocketUpgrade`，服务端收到客户端消息后直接 `close(1000, null)`，断言客户端在一个短超时（如 2s）内交回结果。把处理换回 `onClosed` 时，这个测试会超时失败。

排查：遇到「服务端已经关了连接，客户端却一直在等」，先看监听器有没有实现 `onClosing`。

## 相关链接

- OkHttp 源码 `RealWebSocket.onReadClose`（4.12.0；其它版本未验证）
- 同一场景的另一个坑：腾讯智聆口语评测 Android SDK 建连竞态（`kotlin/2026-10-10-tencent-soe-buffer-source-race.md`）
- 项目内记录：私有仓库 Issue #346 / PR #347
