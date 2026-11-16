---
title: "Blender 循环单帧渲染重复开销过高，改用连续动画渲染"
stack: "common"
platform: []
versions: ["Blender 5.2", "EEVEE"]
tags: ["blender", "eevee", "animation", "render", "performance"]
project: "local-media-pipeline"
status: solved
date: "2026-11-16"
---

## 现象

在 macOS Apple Silicon、10 逻辑核、16 GB 内存的环境中，使用 EEVEE 渲染小尺寸透明角色动画。Python 逐帧调用 `scene.frame_set(frame)`，再反复执行 `bpy.ops.render.render(write_still=True)`，每帧仍需约 9 秒。

对同一场景、同一组 10 帧原生关键帧、512 × 256 RGBA、8 samples 做对照：

| 调用方式 | 实测耗时 |
| --- | --- |
| 每帧单独调用 `write_still=True` | 稳态约 8.6–9.3 秒/帧 |
| 一次调用 `animation=True` | 首帧 8.713 秒；后 9 帧平均 0.17784 秒/帧 |

追加 640 × 320、60 帧基准：单进程稳态平均 0.16997 秒/帧；两个进程各渲染不重叠的 60 帧，分别为 0.19036、0.19078 秒/帧，合计稳态吞吐约为单进程的 1.78 倍。

## 原因

单变量实验表明，瓶颈与反复发起独立单帧渲染有关，而不是输出像素量本身。推断独立调用重复承担渲染引擎初始化及缓存准备开销，连续动画渲染则能复用引擎和缓存。未做 Blender 内部调用栈分析，缓存复用机制属于推断；上述计时差异是实测结果。

## 解决方案

先将身体动作、表情和音频驱动的口型烘为 Blender 原生关键帧，让场景在指定帧自行得到正确状态。随后设置连续帧区间和输出序列前缀，只调用一次动画渲染：

```python
import bpy

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 300
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.filepath = '//frames/frame_'
bpy.ops.render.render(animation=True)
```

保存 `.blend`，并确认输出目录已准备好；`//` 相对于该文件所在目录。若原流程依赖外层 Python 循环逐帧改写对象状态，不能只删除循环后直接调用 `animation=True`，应先把这些状态烘为关键帧，并抽查动作、表情和口型。

需要并行时，先做短区间吞吐和内存基准。确认资源允许后，由独立进程渲染不重叠帧区间，并保证每帧输出文件名唯一，避免抢写同一文件。比较总完工时间时计入各进程首帧初始化开销。

本记录的提速数据只适用于这次机器、场景与版本，不能作为其他显卡、Blender 版本或复杂场景的固定性能承诺。

## 相关链接

- [Blender Python API：Render Operators](https://docs.blender.org/api/current/bpy.ops.render.html)：`bpy.ops.render.render` 的动画与单帧渲染参数。
