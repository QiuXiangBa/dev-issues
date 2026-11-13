---
title: "Blender 缓存关键帧 RNA 引用后删除导致重复烘焙报错"
stack: "common"
platform: []
versions: ["Blender 5.2.0 LTS", "macOS Apple Silicon", "Blender Python FCurve.keyframe_points"]
tags: ["blender", "python", "fcurve", "keyframe", "rna", "animation"]
project: "Blender 工具流程"
status: "solved"
date: "2026-11-13"
---

## 现象

第一次向指定 F-Curve 区间写入关键帧成功，第二次重新烘焙同一区间、删除已有关键帧时失败：

```text
RuntimeError: Keyframe not in F-Curve
```

出问题的删除方式先把集合转换为 Python 列表，再依次移除列表中保存的 RNA 元素：

```python
for key in list(fc.keyframe_points):
    if first_frame <= key.co.x <= last_frame:
        fc.keyframe_points.remove(key, fast=True)
fc.update()
```

## 原因

`list(fc.keyframe_points)` 保存的是 Blender RNA 元素引用，并不是独立的关键帧数据副本。移除元素后，底层集合发生变化，之前缓存的引用可能不再对应集合中的当前有效元素。

因此，即使 Python 列表本身没有变化，也不能继续假设其中所有 RNA 引用仍适合传给 `remove`。本次问题出现在修改同一 F-Curve 集合时，不能据此认定普通 Python 列表遍历也有相同限制。

## 解决方案

倒序遍历实时索引，每次从当前集合重新取出元素，然后立即删除。不要把多个待删除的 RNA 元素提前缓存下来。

```python
def remove_keys_in_range(fc, first_frame, last_frame):
    for index in range(len(fc.keyframe_points) - 1, -1, -1):
        key = fc.keyframe_points[index]
        if first_frame <= key.co.x <= last_frame:
            fc.keyframe_points.remove(key, fast=True)
    fc.update()
```

倒序移除使尚未处理的较小索引保持有效；每次实时取值则避免继续使用删除前缓存的元素引用。这里保留 `fast=True`，统一在结束后调用 `fc.update()`。

## 验证与适用边界

对同一个对象、同一个区间连续烘焙三次，均成功完成：

- 三次生成的关键帧帧号、值和插值模式一致。
- 所选区间之外已有关键帧的帧号、值和插值模式保持。
- 其他对象的关键帧与未被选中的动画通道保持。
- 验证过程未保存回原始工程，源文件哈希不变。

Blender 的 `AUTO` 手柄位置可能因相邻关键帧变化而重新计算。本验证没有宣称区间外手柄坐标或整个区间外连续曲线形状完全不变。该结论针对 Blender 5.2.0 LTS 的这条修改路径，其他版本仍需实际复测。

## 相关链接

- [Blender FCurveKeyframePoints API](https://docs.blender.org/api/current/bpy.types.FCurveKeyframePoints.html)：关键帧集合与 `remove` 接口参考。
- [Blender FCurve API](https://docs.blender.org/api/current/bpy.types.FCurve.html)：`update()` 接口参考。

API 链接用于查阅接口定义；RNA 引用失效现象及修复结果来自实际重复烘焙验证，不声称官方文档已确认同一报错。
