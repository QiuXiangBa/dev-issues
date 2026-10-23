---
title: "VectorDrawable 单条 pathData 超过 32,767 字节：编译不报错，运行时 PathParser 读串崩溃"
stack: "kotlin"
platform: [android]
versions: ["agp 8.11.1", "compose-bom 2025.06.00 (ui 1.8.x)", "kotlin 2.1.20", "android 17 emulator"]
tags: [vectordrawable, pathdata, aapt2, resources, string-pool, compose, svg, figma]
project: "xuejieai"
status: solved
date: "2026-10-23"
---

## 现象

把 Figma 导出的 logo SVG（白色字形 + 蓝色「外描边」，Figma 用 `<mask>` 实现）转成 VectorDrawable，`<path android:pathData="…">` 照搬 SVG 的 `d`。`assembleDebug` 成功、AAPT2 没有任何警告，页面一进就崩：

```
java.lang.IllegalArgumentException: Unknown command for: R
    at androidx.compose.ui.graphics.vector.PathNodeKt.addPathNodes(PathNode.kt:243)
    at androidx.compose.ui.graphics.vector.PathParser.pathStringToNodes(PathParser.kt:143)
    at androidx.compose.ui.graphics.vector.compat.XmlVectorParser_androidKt.parsePath(XmlVectorParser.android.kt:275)
    at androidx.compose.ui.res.PainterResources_androidKt.painterResource(PainterResources.android.kt:69)
```

XML 里根本没有 `R` 这个字符。出事的那条 `pathData`（Figma 展开后的描边轮廓）有 48,638 字节；另一条 6k 的字形路径没事。

## 原因

Android 资源字符串池（`ResStringPool`）UTF-8 编码的长度字段只有 2 字节、最高位当标志位，**单条字符串上限 0x7FFF = 32,767 字节**（字符数与字节数两个长度都受此限）。AAPT2 不校验，超长的字符串在运行时被截断 / 读到了池里后面别的内容，解析成了莫名其妙的命令字母。framework 的 `VectorDrawable` 和 Compose 的 `XmlVectorParser` 读的是同一份字符串，都会出事。

Figma 导出的「展开描边」是密集折线（几百个子路径、每个点 6 位有效数字），很容易超过这个上限。

## 解决方案

分三步把路径压到上限以内（写成一次性 Python 脚本，只处理 SVG 用到的绝对命令 M / L / C / H / V / Z）：

1. **降精度 + 简化**：坐标四舍五入到 0.01（104 单位宽的画布上 < 0.05px）；连续 L 折线段做 RDP 简化（容差 0.02）；省掉多余分隔符（负数自带分隔、同命令连续时省略命令字母）。48k → 约 33k，还不够。
2. **拆成多个 `<path>`**：子路径（每个 `M…Z`）按「轮廓包围盒两两相交」用并查集归组，每组一个 `<path>`（同一 `fillColor`）。互相嵌套 / 重叠的轮廓（字形和它的孔洞）一定在同一组，nonzero 填充语义不变；不同组之间没有任何一对轮廓相交，拆开画结果相同。注意拆出来的几个 path **整体**包围盒仍可能相交，不变量是「轮廓两两不相交」。

   ```python
   groups = subpaths(tokens)                      # 每个 M…Z 一组
   boxes = [bbox(g) for g in groups]
   for i, j in combinations(range(len(groups)), 2):
       if intersects(boxes[i], boxes[j], margin=0.05):
           union(i, j)
   paths = [encode(concat(members)) for members in clusters()]
   assert all(len(p.encode()) < 30_000 for p in paths)   # 给 32,767 留余量
   ```
3. **mask 外描边的等价画法**：VectorDrawable 不支持 `<mask>`。先画描边轮廓（Figma 已导出为展开后的填充路径，字形内外两侧都有），再把字形盖在上面遮掉内侧，视觉等价。

另外给 `<vector>` 加 `tools:ignore="VectorPath"` 抑制 lint 的「路径过长（> 800 字符）」提示，这是有意为之。

校验：把生成的几条 path 拼回一个 SVG，与原 SVG 在无头 Chrome 里以 12× 同屏渲染做像素 diff（607,500 像素里 154 个差值 > 64，全在描边边缘的抗锯齿差）。

## 相关链接

- AOSP `frameworks/base/libs/androidfw/ResourceTypes.cpp` 的 `decodeLength`：UTF-8 字符串池长度编码上限 0x7FFF
