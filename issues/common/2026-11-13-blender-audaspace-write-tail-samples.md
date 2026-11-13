---
title: "Blender Audaspace Sound.write 重采样导出末尾多出非静音样本"
stack: "common"
platform: []
versions: ["Blender 5.2.0 LTS", "macOS Apple Silicon", "Blender bundled Python aud"]
tags: ["blender", "audaspace", "audio", "resampling", "pcm", "sample-count"]
project: "Blender 工具流程"
status: "workaround"
date: "2026-11-13"
---

## 现象

在 Blender 5.2.0 LTS / macOS Apple Silicon 中，将一段 24000 Hz、83688 样本（3.487 秒）的单声道 WAV，通过 `aud.Sound(...).write(...)` 导出为 16000 Hz PCM WAV：

- 按时长计算应有 `83688 × 16000 / 24000 = 55792` 个样本。
- 实际导出 58336 个样本（3.646 秒），多出 2544 个样本（0.159 秒）。
- 额外尾部并非全部静音，可能让按分析音频生成的时间戳或后续动画延长。

复现调用形式如下，文件名为通用示例：

```python
import aud

aud.Sound("input.wav").write(
    "analysis.wav", 16000, 1,
    aud.FORMAT_S16, aud.CONTAINER_WAV, aud.CODEC_PCM,
    0, 4096,
)
```

## 原因

已确认差异出现在该输入和调用方式的导出尾部，尚未检查 Audaspace 内部实现，因此不能将缓存、块对齐或重采样器延迟认定为根因。

独立 FFmpeg 重采样得到 55792 个样本。在原始有效时长内，两份输出的相关系数约为 0.999943，时移为 0；这支持“差异集中在导出末尾”的观察，不证明所有输入都会出现同样问题。

## 解决方案

绕过此处的 `Sound.write` 导出路径：先取得重采样后的数组，再明确转换为 16-bit little-endian PCM，用 Python 标准库 `wave` 写入。

```python
from pathlib import Path
import wave
import aud
import numpy as np


def write_analysis_pcm(source, destination, sample_rate=16000):
    data = aud.Sound(str(source)).rechannel(1).resample(sample_rate, 3).data()
    mono = np.asarray(data).reshape(-1)
    pcm = np.clip(np.rint(mono * 32768.0), -32768, 32767).astype("<i2")

    with wave.open(str(destination), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return len(pcm)


count = write_analysis_pcm(Path("input.wav"), Path("analysis.wav"))
```

不要仅凭播放器显示的秒数判断成功，应重新读取输出 WAV 的采样率与帧数。需要精确时长时，还应与已知源样本数及独立工具结果对照。

## 验证与适用边界

- 同一转换流程实际运行两次，输出均为 16000 Hz、55792 个样本。
- 使用生成的分析音频驱动后续时间线时，音频结束后的控制参数正确归零。
- 仅记录上述版本、输入和参数下的已复现行为；没有验证所有音频格式、Blender 版本或 `write` 参数。
- 这是已验证的规避方案，不声称修复 Audaspace 内部缺陷。

## 相关链接

- [Blender 5.2 Audio System（aud）API](https://docs.blender.org/api/5.2/aud.html)：接口定义参考；本文尾样本异常及数值来自本地实测，不是文档对该缺陷的确认。
