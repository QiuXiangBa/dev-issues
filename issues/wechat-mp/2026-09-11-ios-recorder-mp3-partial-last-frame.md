---
title: iOS 微信 RecorderManager 录的 mp3 末尾是残帧、wav 长度字段错误，严格校验的服务端 400
stack: wechat-mp
platform: [wechat, ios]
versions: [基础库 3.17.3, iOS 18.7.2, 微信开发者工具 2.02.2608060]
tags: [recorder-manager, getrecordermanager, mp3, wav, uploadfile, asr, audio-validation, ios]
project: <小程序项目>
status: solved
date: 2026-09-11
---

## 现象

真机（iOS）用 `wx.getRecorderManager()` 录音后 `wx.uploadFile` 上传给服务端做语音识别，服务端返回：

```
{"success":false,"code":400,"msg":"请上传完整MP3，或16kHz单声道16位PCM编码的WAV录音"}
```

录音参数 `{ duration: 59000, sampleRate: 16000, numberOfChannels: 1, encodeBitRate: 48000, format: 'mp3' }`，换 `format: 'wav'` 同样 400。而用第三方工具生成的标准 MP3 / WAV 走同一段上传代码都 200。

在真机调试 Console 里各录 3 秒并逐字节扫描文件：

| 格式 | 文件结构 |
|---|---|
| mp3 | 16376 字节，76 个 MPEG-2 Layer III 帧（16kHz / 48kbps），逐帧累加应为 16416 字节：**最后一帧少 40 字节，是个残帧**；文件头无 ID3、无垃圾字节 |
| wav | 96404 字节，`data` 块长度字段写成 96404（等于整个文件大小），实际数据 96360；RIFF 长度字段也多 44（正好一个 44 字节头） |

## 原因

两边各有一半：

- iOS 微信录音器的输出本身不规范。MP3 停止时最后一帧没写完整就收尾；WAV 头里的长度字段按整个文件长度填，没减掉头。腾讯云 / 大多数解码器都能容忍这些，所以平时没人发现。
- 服务端做了严格的前置校验。用样本变体实测其规则：MP3 必须从头到尾全是完整帧（末尾半帧、首尾多零字节都拒，前置 ID3 标签可以）；WAV 的 RIFF / data 长度字段必须和实际字节数完全一致（多带 LIST 块可以）。

## 解决方案

服务端能改就放宽校验（容忍末尾不足一帧的尾巴、按实际字节数判 WAV 长度）。客户端要自己兜底的话，上传前修文件：

**MP3：逐帧扫描，只保留连续的完整帧。** 纯函数，Layer III 帧长 = `(MPEG-1 ? 144 : 72) * bitrate / sampleRate + padding`：

```js
const BITRATES = {
  1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
  2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
const SAMPLE_RATES = { 3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000] }

function frameLength(b, pos) {
  if (b[pos] !== 0xff || (b[pos + 1] & 0xe0) !== 0xe0) return 0
  const version = (b[pos + 1] >> 3) & 3, layer = (b[pos + 1] >> 1) & 3
  const bitrateIndex = b[pos + 2] >> 4, sampleRateIndex = (b[pos + 2] >> 2) & 3, padding = (b[pos + 2] >> 1) & 1
  if (version === 1 || layer !== 1 || bitrateIndex === 0 || bitrateIndex === 15 || sampleRateIndex === 3) return 0
  const bitrate = BITRATES[version === 3 ? 1 : 2][bitrateIndex] * 1000
  return Math.floor((version === 3 ? 144 : 72) * bitrate / SAMPLE_RATES[version][sampleRateIndex]) + padding
}

/** 返回只含完整帧的新 ArrayBuffer；一帧都没有（点按过短）返回 null */
function trimToCompleteFrames(buffer) {
  const b = new Uint8Array(buffer)
  let start = -1, end = 0, frames = 0, pos = 0
  while (pos + 4 <= b.length) {
    const len = frameLength(b, pos)
    if (!len) { if (start >= 0) break; pos += 1; continue }   // 首帧前的 ID3 / 垃圾逐字节跳过，帧流开始后遇到非帧就停
    if (pos + len > b.length) break                            // 残帧
    if (start < 0) start = pos
    pos += len; end = pos; frames += 1
  }
  return frames ? b.slice(start, end).buffer : null
}
```

`onStop` 里：

```js
const fs = wx.getFileSystemManager()
const trimmed = trimToCompleteFrames(fs.readFileSync(res.tempFilePath))
if (!trimmed) return handleSilence()
const path = wx.env.USER_DATA_PATH + '/asr-upload.mp3'   // 每次覆盖
fs.writeFileSync(path, trimmed)
wx.uploadFile({ url, filePath: path, name: 'file', header: authHeader() })  // 登录态头按各自项目的封装来
```

真机验证：76 帧的录音裁成 75 帧后 200；把之前被拒的「末尾截断半帧」「首尾各加零字节」两个样本用同一函数处理后也都 200。注意帧头第 3 个字节（下标 2）才是 bitrate / sampleRate / padding，第 4 个字节是声道模式，写测试时别放错位。

**WAV 路线：自己重写 44 字节头。** 采样数据是对的，只有头错：找到 `fmt ` 和 `data` 块，按实际 PCM 长度重新写 RIFF 大小（文件长 − 8）和 data 大小（文件长 − 44）。代价是 16k 单声道 16 位 60 秒约 1.9MB，比 MP3 大 6 倍。

**真机探针**：在开发者工具「真机调试」的 Console 里粘贴一段脚本，录 3 秒 → `readFileSync` → 扫帧 / 解 RIFF → `console.log` 摘要 → 顺手 `uploadFile` 看服务端回什么，一次就能拿到文件结构和服务端结论，比猜快得多。

## 相关链接

- 微信官方文档 RecorderManager.start：https://developers.weixin.qq.com/miniprogram/dev/api/media/recorder/RecorderManager.start.html
- MP3 帧头格式：http://www.mp3-tech.org/programmer/frame_header.html
- 配套问题：同库 `wechat-mp/2026-09-11-devtools-recorder-outputs-webm.md`（模拟器录音根本不是 MP3）

## 更新 2026-11-17

本节收紧原「解决方案」中 MP3 / WAV 修复示例的适用范围。原始样本数据和历史代码保留；复用时以下述限制为准，不把示例视为任意 MP3 / WAV 的通用修复器。

### MP3：仅适用于已确认无标签、无前缀的录音帧流

原始录音样本已经确认“文件头无 ID3、无垃圾字节”。原 `trimToCompleteFrames` 示例仅适用于这类**第 0 字节就开始 MPEG Layer III 帧流**、编码格式由原 `frameLength` 支持的录音输入。

- 这个输入限制需要调用方在使用前确认；原函数逐字节扫描的写法**没有自动保证**它。不要把含 ID3 标签、内嵌图片、未知前缀、任意附加元数据或未知损坏的 MP3 直接交给它。
- 逐字节寻找同步位不能替代 ID3 解析：标签里的二进制数据可能恰好包含看起来合法的帧头，原函数可能把伪帧当成首帧，随后提前停止并误裁真正的音频。
- 需要支持带标签或其他来源的 MP3 时，应换用可靠的格式解析器，按 ID3 版本和标签长度等规则跳过完整标签，并验证音频帧的连续性；不能仅靠搜索 `0xFF` 同步位扩展这段示例。
- 原文对“首尾加零字节”样本的处理仅是历史实验结果，不构成对任意前缀的兼容承诺。无法确认上述输入条件时，不应用此函数裁剪，应先正确解析或拒绝该输入。

因此，本次选择补齐**受限输入前提**，没有把原示例升级为支持 ID3 或任意损坏文件的通用解析器。

### WAV：不能普遍使用“文件长度减 44”作为 data 长度

原文 `data 大小 = 文件长 - 44` 只适用于**标准 44 字节头、无额外块、data 后都是 PCM 采样数据**的那类样本，不适用于所有 RIFF/WAVE 文件。

- WAV 可以包含扩展 `fmt `、JUNK、LIST 等块，以及块之间的对齐填充。这些字节不是 PCM 数据，不能一并写入 data 长度。
- 一般情况下应识别实际的 `fmt ` 与 `data` 区域，核对格式、边界和块对齐，以**已确认的 PCM 数据字节数**写入 data 长度；RIFF 长度则按最终输出文件的实际长度减 8 写入。
- 若明确要重建标准 44 字节 PCM WAV，应只输出“新的 44 字节头 + 已识别的 PCM 数据”，此时才有 `dataSize = pcmBytes.length`、`riffSize = outputFileBytes - 8`，且输出文件长度为 `44 + pcmBytes.length`。不要把原文件中的额外块当作音频直接拼入。
- 当原始长度字段已损坏、又无法可靠确定 PCM 与其他块的边界时，不能猜测 data 长度或直接套用减 44；应使用可靠解码器识别后重新编码，或报告无法安全修复。

本次更新仅做静态审阅与适用范围修正，未重新录音，也未复跑原文的真机或服务端测试。原文中的“200”应结合实际 HTTP 状态与响应体业务结果判断，不能仅凭状态数字认定业务成功；详见配套记录同日更新。
