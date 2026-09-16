---
title: "Figma 旋转存储的画板：多层 SVG 素材用 JSX 转 HTML 整页反旋转后 WKWebView 光栅化"
stack: "ai-tools"
platform: [ios, web]
versions: [claude-code 2.1.252, figma-plugin 2.2.111, figma-dev-mode-mcp 1.0.0, tailwindcss-browser 4.3.3, xcode 27.0]
tags: [figma, mcp, design-to-code, svg-rasterize, wkwebview, tailwind, rotated-artboard, claude-code]
project: "tutuai"
status: solved
date: "2026-09-16"
---

## 现象

设计师把横屏画板（1194×834）的内容整体旋转 90° 存储（画板本身是横的，子节点全部带 90° 旋转，坐标在 834×1194 的竖向空间里）。用 Figma MCP `get_design_context` 做 design-to-code 时：

- 返回的 React + Tailwind 里每个叶子都套着 `flex items-center justify-center` + `flex-none h-[100cqw] rotate-90 w-[100cqh]` 的容器查询 wrapper，位置全是相对整个画板的百分比 `inset-[25.63%_27.52%_45.73%_31.47%]`，还混着 `-scale-y-100 rotate-[-105.03deg]`、`h-[hypot(21.1325cqw,78.8675cqh)]`。
- 一个插画（唱片、唱臂、三颗星）由 10 到 14 个独立 SVG 叠成，逐个手工把 CSS 换算成横屏坐标再判断每张 SVG 的朝向，极易出错；`get_screenshot` 单节点截图会把背景和兄弟节点烘焙进去，不能当透明素材。
- 部分叶子 SVG 的 codegen 是「拉伸」的（11×15 的 SVG 被放进 15×11 的盒子里，没有 rotate wrapper），说明 codegen 对旋转叶子的处理不一致，不能只信一种规则。

## 原因

codegen 输出的 HTML/CSS 已经是浏览器可以正确渲染的完整描述（含所有旋转、翻转、百分比定位、遮罩），错误只出在人工把它翻译成另一套坐标的过程。只要把这段 JSX 几乎原样交给浏览器渲染，再把整页反向旋转 90°，朝向和位置就由浏览器算，横屏坐标 = 设计稿坐标，不需要任何手工换算。

## 解决方案

1. 下载素材，**文件名必须用 URL 里的 hash**（`http://localhost:3845/assets/<hash>.svg` → `svg/<hash>.svg`），HTML 里引用 `../svg/<hash>.svg`。起别名会导致 `<img>` 静默不加载，输出只剩一圈破图边框（判别：alpha 直方图全在 0 附近但边缘有一圈不透明像素）。

2. 拉一份 Tailwind 浏览器版到本地（不能依赖 CDN 实时加载，WKWebView 用 file:// 打开）：

```bash
curl -s -o tools/tw.js https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4
```

它支持 codegen 用到的全部任意值：`inset-[..%]`、`rotate-90`、`-scale-y-100`、`h-[100cqw]`、`hypot()`、`mask-*`。

3. 外壳 HTML：横屏 `#stage` 里放一个和画板竖向空间同尺寸的 `#art`，反旋转 90°。子树里 `display: contents` 的百分比 inset 是相对整个画板的，所以 `#art` 尺寸必须精确等于画板竖向空间。

```html
<script src="../tools/tw.js"></script>
<style>
html,body{margin:0;background:transparent;overflow:hidden}
#stage{position:absolute;left:0;top:0;width:1194px;height:834px}
#art{position:absolute;left:0;top:0;width:834px;height:1194px;
     transform-origin:0 0;transform:translate(0,834px) rotate(-90deg)}
</style>
<div id="stage"><div id="art">
  <!-- 把 get_design_context 的 JSX 子树粘进来：className→class，
       style={{maskImage:`url("${x}")`}}→style="mask-image:url('../svg/<hash>.svg')"，
       style={{containerType:"size"}}→style="container-type:size"，{img}→路径 -->
</div></div>
```

旋转方向校验：竖向空间里 `(left, top, w, h)` 的元素在横屏落在 `x = top, y = 834 − left − w, w = h, h = w`；和 `get_metadata` 里一两个已知节点（返回按钮等）对一下即可。

4. 光栅化 + 裁切。用 WKWebView 透明底快照（几十行 Swift，`swiftc -O` 编译；`takeSnapshot` 前等 2.5 s 让 Tailwind 编译完、图片加载完），然后按横屏坐标 ×3 裁：

```bash
rasterize page.html 1194 834 3 raw.png
sips -c $((h*3)) $((w*3)) --cropOffset $((y*3)) $((x*3)) raw.png --out asset-3x.png   # 拷进 xcassets 时再按 Xcode 规则改名为 3x 后缀
```

出血到画板外的素材给 `#stage` 加 margin，裁切坐标加同样的 margin。裁切框可以比可见像素大一点：透明留白无害，而且素材摆放位置就是裁切框，不用再量。

5. 朝向判别口诀：有 rotate wrapper 或独立 `<img>` 摆在画板上的 SVG 走整页反旋转；被 codegen「拉伸」进反比例盒子、且没有 rotate wrapper 的叶子（组件里的图标矢量）本身就是正向的，直接按原尺寸渲染不旋转。不确定就两种都渲染一次看图。

6. 检查工具：写一个 CoreGraphics 小工具输出 alpha 包围盒、alpha 直方图，并把透明图叠到深色底上看（透明 PNG 直接预览是白底，白色素材看不见）。

## 相关链接

- 前置记录（桌面端本地 MCP、基础光栅化、`loadFileURL` 读权限坑）：issues/ai-tools/2026-09-16-figma-mcp-unauthorized-use-desktop-dev-mode.md
- Tailwind CSS 浏览器版：https://tailwindcss.com/docs/installation/play-cdn
- 项目内落地：QiuXiangBa/tutuai-app#33 / PR #34（唱片盘、唱臂、三星、火花、沙滩、音频场景等 15 张 3x 图全部由此流水线产出）
