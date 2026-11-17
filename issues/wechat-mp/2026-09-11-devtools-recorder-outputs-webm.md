---
title: 开发者工具模拟器 RecorderManager 录出的 mp3 / wav 实际是 WebM，服务端按内容校验必失败
stack: wechat-mp
platform: [wechat]
versions: [微信开发者工具 2.02.2608060, 基础库 3.17.3]
tags: [devtools, simulator, recorder-manager, getrecordermanager, uploadfile, webm, mp3, asr]
project: <小程序项目>
status: solved
date: 2026-09-11
---

## 现象

小程序用 `wx.getRecorderManager()` 录音（`format: 'mp3'`，16k 单声道），`onStop` 后把 `tempFilePath` 用 `wx.uploadFile` 传给服务端做语音识别。在开发者工具模拟器里录完上传，服务端稳定返回：

```
{"success":false,"code":400,"msg":"请上传完整MP3，或16kHz单声道16位PCM编码的WAV录音"}
```

改 `format: 'wav'` 结果一样。同一段代码在真机上录出的文件是正常 MP3。

附带两个迷惑点：

- 模拟器的 Network 面板把这条 `wx.uploadFile` 请求显示成 `Request Method: GET`、`Status Code: 200`，容易误判成没走 POST。用同一 token 直接发 GET，服务端回的是「当前方法不支持GET请求」，文案不同，说明面板显示的方法不可信。
- 模拟器文件系统目录（`~/Library/Application Support/微信开发者工具/<hash>/WeappSimulator/WeappFileSystem/<openid>/<appid>/tmp`）里找不到录音文件，录音结果不落盘在这里。

## 原因

开发者工具的 RecorderManager 是用浏览器 `MediaRecorder` 实现的。从 `app.asar` 里能直接读到：

```js
navigator.mediaDevices.getUserMedia(this.constraints).then(stream => {
  this.mediaRecorder = new MediaRecorder(stream, this.options)
  this.mediaRecorder.onstop = () => {
    const blob = new Blob(this.recordedBlobs, { type: "audio/webm" })
    // ... saveBase64DataToFile(project, base64, `.durationTime=${duration}.${format}`)
  }
})
```

也就是不管 `format` 传 `mp3` 还是 `wav`，内容都是 WebM/Opus，`format` 只决定文件后缀。工具停止录音时还会弹一条 `RECORD_FORMAT_INFO` 提示，说明官方知道这一点。任何按音频内容（帧头、RIFF 头）校验的服务端都会拒掉。

另外这台 Mac 没有音频输入设备时，模拟器 `start()` 直接回 `operateRecorder:fail NotFoundError`（`getUserMedia` 找不到设备），不会走到 `onStop`。

## 解决方案

1. 涉及录音内容的功能（语音识别、上传录音）只在真机验收：预览版或「真机调试」。真机调试的 Console 可以直接粘贴 JS 执行，方便做探针。
2. 要在模拟器里验证「上传 + 服务端」这一段是否接对，绕过录音：把已知合法的样本文件拷进模拟器的用户目录（磁盘路径 `WeappSimulator/WeappFileSystem/<openid>/<appid>/usr/`，对应小程序里的 `wx.env.USER_DATA_PATH`），再在逻辑层执行 `wx.uploadFile({ filePath: wx.env.USER_DATA_PATH + '/sample.wav', ... })`。样本能 200 就说明接法没问题，剩下的就是文件本身。
3. 不要用模拟器 Network 面板显示的 Request Method 判断请求方式；要确认就直接发一条对照请求看服务端文案，或抓包。
4. 在文档里写明「模拟器录音 = WebM」，否则每个新接手的人都会在这里丢半天。

## 相关链接

- 微信官方文档 RecorderManager：https://developers.weixin.qq.com/miniprogram/dev/api/media/recorder/RecorderManager.html
- 配套问题：同库 `wechat-mp/2026-09-11-ios-recorder-mp3-partial-last-frame.md`（真机录音文件首尾元数据不规范）

## 更新 2026-11-17

### 修正上传成功的判据

本节修正原「解决方案」中“样本能 200 就说明接法没问题”的表述；原始复现数据保留，不把 HTTP 200 当作业务成功。

- 必须同时检查实际上传响应的 HTTP 状态和响应体：HTTP 状态应符合接口约定的成功范围，响应体的 `success` / `code` 也必须按该接口契约表示成功。不能只看 Network 面板的 200，也不能仅因进入 `wx.uploadFile` 的 success 回调就认定服务端接受了录音。
- 本文已经存在 HTTP 200、响应体 `success:false` / `code:400` 的反例。这属于业务拒绝，不是上传验收通过；业务成功码以接口契约为准，不在这里假定一定为 0 或 200。
- 如 `res.data` 为 JSON 字符串，应先解析，再检查业务结果。无法解析或业务结果明确失败时，不能按“样本上传成功”处理。
- 已知合法样本同时满足 HTTP 与业务成功条件，只能说明**该样本在本次请求中的上传和服务端处理链路可用**，不能据此保证其他格式、其他录音文件或后续识别结果都正常。

本记录中的模拟器行为对应原文列明的开发者工具与基础库版本，不将其推广为所有版本的固定行为。本次更新为静态复核修正，未重新执行录音、真机或服务端验证，也不新增历史实测结论。
