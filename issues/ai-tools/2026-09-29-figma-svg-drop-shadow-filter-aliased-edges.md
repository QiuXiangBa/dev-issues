---
title: "Figma 导出 SVG 的硬投影滤镜（hardAlpha + feOffset）光栅化后边缘锯齿：改画实体偏移副本"
stack: "ai-tools"
platform: [ios, web]
versions: [figma-desktop 126.9.10, figma-plugin 2.2.120, xcode 27.0, macos 26.6.2]
tags: [figma, svg, drop-shadow, filter, svg-rasterize, wkwebview, antialiasing, design-to-code]
project: "tutuai"
status: solved
date: "2026-09-29"
---

## 现象

设计稿里一个带「投影 radius 0、offset (0, 6)」效果的小图标（55×54），Figma Dev Mode MCP `get_design_context` 给出的 SVG 把投影表达成滤镜：

```svg
<g id="body" filter="url(#filter0_d_2938_11398)">
  <ellipse … fill="#F9BB3D"/>
  <path d="…" stroke="#FF8808" stroke-width="3"/>
</g>
<defs>
<filter id="filter0_d_2938_11398" x="0" y="0" width="50" height="61" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
  <feFlood flood-opacity="0" result="BackgroundImageFix"/>
  <feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha"/>
  <feOffset dy="6"/>
  <feComposite in2="hardAlpha" operator="out"/>
  <feColorMatrix type="matrix" values="0 0 0 0 1 0 0 0 0 0.531889 0 0 0 0 0.0314941 0 0 0 1 0"/>
  <feBlend mode="normal" in2="BackgroundImageFix" result="effect1_dropShadow_2938_11398"/>
  <feBlend mode="normal" in="SourceGraphic" in2="effect1_dropShadow_2938_11398" result="shape"/>
</filter>
</defs>
```

用 WKWebView 把它光栅化成 @3x PNG（165×180）后，**本体外圈和投影边缘全是阶梯状锯齿**，缩到 1x 看就是「边缘发毛」；用户反馈「图标不完整且有瑕疵」。同一个 SVG 只去掉 `filter` 属性再出图，边缘就是平滑的。

判别方法：把两版 @3x 图用 `<img style="image-rendering:pixelated;width:660px">` 并排放大 4 倍再截一次，锯齿一眼可见。

## 原因

Figma 的 drop-shadow 导出用 `feColorMatrix` 把 SourceAlpha 乘 127 压成二值 alpha（`hardAlpha`），再用 `feComposite operator="out"` 抠掉本体区域。这条链在 WebKit 里按位图逐像素处理、不抗锯齿；整个带 `filter` 的组都会经过滤镜合成，所以不止投影，本体的外缘也跟着发毛（推断：滤镜区域按整数像素栅格化）。设计稿里 radius 0 的「硬投影」本质上就是本体的纯位移副本，根本不需要滤镜。

## 解决方案

1. 删掉本体组上的 `filter="url(#…)"` 和 `<defs>` 里的滤镜，在本体前面画一份位移副本，fill 和 stroke 都用投影色。本体不透明时视觉与滤镜版完全一致，边缘由普通几何抗锯齿：

```svg
<svg width="55" height="60" viewBox="0 0 55 60" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g id="shadow" transform="translate(0 6)">
    <ellipse … fill="#FF8808"/>
    <path d="…" fill="#FF8808" stroke="#FF8808" stroke-width="3"/>
  </g>
  <g id="body">
    <ellipse … fill="#F9BB3D"/>
    <path d="…" stroke="#FF8808" stroke-width="3"/>
  </g>
  …
</svg>
```

2. `viewBox` / `width` / `height` 要把投影范围算进去（上例 54 + 6 = 60），否则投影被裁掉。

3. 有模糊半径的软投影不能这样替换（未验证），别套用；只对 radius 0 的硬投影这么做。

4. 出图后用第「现象」节的像素放大法对比一次再入库；顺手补 @2x（iPad 全是 2x 设备，只放 @3x 运行时还要再缩一次）。

5. 旋转存储画板的补充（见相关记录）：图标节点导出的 SVG 同样是竖排的（SVG 宽高 = 节点高 × 节点宽 + 投影长度，与 `get_metadata` 的横屏 w/h 互换），整页转 −90° 后投影方向要跟着转：滤镜版 `feOffset dy="6"` 改 `dx="-6"`，实体副本版 `translate(0 6)` 改 `translate(-6 0)`，`viewBox` 相应左移。方向对不对以出图为准。

## 相关链接

- 前置记录（旋转画板 JSX → HTML 整页反旋转 → WKWebView 光栅化流水线）：issues/ai-tools/2026-09-16-figma-rotated-artboard-svg-assets-via-html.md
- 项目内落地：QiuXiangBa/tutuai-app#179 / PR #180（家长验证弹框旋钮图重导）
