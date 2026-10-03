---
title: "rpx 向下取整成整数 px，按盒子拉伸的 SVG 背景图被等比缩小、两端图形往里挪"
stack: "wechat-mp"
platform: [wechat]
versions: [微信开发者工具 2.02.2608060, 基础库 3.17.2]
tags: [rpx, wxss, svg, data-uri, background-size, preserveaspectratio, pixel-rounding, layout]
project: "<小程序项目>"
status: solved
date: "2026-10-03"
---

## 现象

没有任何报错，只是版面对不上设计稿。

一条装饰用 inline SVG data URI 做背景图：viewBox 宽 204.68、高 7.30，左右两端各有一颗小星。盒子按「设计稿 px × 2 = rpx」写：

```css
.rule {
  width: 409.4rpx;   /* 204.7px */
  height: 14.6rpx;   /* 7.3px */
  background-size: 100% 100%;
  background-image: url("data:image/svg+xml;utf8,%3Csvg%20width=%22204.679%22%20height=%227.30185%22%20viewBox=%220%200%20204.679%207.30185%22 ...");
}
```

在 375 宽的开发者工具模拟器上截图逐像素量：两颗星的中心相距 188px，而不是 SVG 里的 196px——两颗星各往中间挪了约 4px，星本身也略小。盒子的位置和宽度是对的，只有图形在盒子里缩了。

伴生现象：小数 rpx 在不同屏宽上的落点不一致。例如 `top: 30.7rpx` 和相邻元素的 `top: 36.8rpx`，在 375 宽上相差 3px（15 与 18），在 390 宽上相差 4px（15 与 19），原本对齐的两个元素在 390 宽上错开 1px。

## 原因

两件事叠在一起：

1. **WXSS 的 rpx 换算结果向下取整成整数 CSS px。** 基础库把 rpx 按 `rpx / 750 × 屏宽` 换算后做 `floor`（带一个很小的 eps 防浮点误差），不保留小数。14.6rpx 在 375 宽上是 7.3px → 7px；409.4rpx 是 204.7px → 204px。这是读基础库 3.17.x 的 JS 换算实现并在模拟器里实测得到的结论；真机若走别的换算路径，取整粒度可能不同，没有验证过，但不应依赖小数 rpx 的精度这一点不变。
2. **带 viewBox 的 SVG 默认 `preserveAspectRatio="xMidYMid meet"`。** `background-size: 100% 100%` 只决定 SVG 视口有多大，视口里的内容仍然等比缩放后居中，不会被拉伸。盒子被取整成 204×7 之后，缩放比 = min(204 / 204.68, 7 / 7.30) = 0.959，整条内容横向也跟着缩 4%，两端的图形各往中间挪约 4px。

所以只要盒子的宽高比和 viewBox 的宽高比因为取整而不一致，等比缩放就会按较小的那个比例缩。细长的图（高度只有几 px）最明显：高度差 0.3px 就是 4%。

## 解决方案

1. 需要「铺满盒子」的 SVG 背景，根节点加 `preserveAspectRatio="none"`，内容就按盒子的实际尺寸拉伸，不再受取整影响：

   ```
   %3Csvg%20width=%22204.679%22%20height=%227.30185%22%20viewBox=%220%200%20204.679%207.30185%22%20preserveAspectRatio=%22none%22%20...
   ```

   Figma 导出的 SVG 本来带这个属性，手工清理 `style` / `id` 等多余属性时别把它一起删掉。图标类（正方形、`background-size: contain`）不需要。

2. 对位置敏感的值别依赖小数 rpx 的精度。按取整后的整数 px 核算，至少把常见屏宽各算一遍（375 / 390 / 393 / 414 / 430）：

   ```
   px = floor(rpx / 750 × 屏宽)
   ```

   上面的例子把 `top: 30.7rpx` 改成 `31rpx`：375 宽不变（15.5 → 15），390 宽变成 16，与相邻元素重新对齐。

3. 两个相邻描边之间只留 1px 时，取整可能把间隙吃成 0（两条线并成一条粗线）。贴边元素要么留 ≥2px 余量，要么按取整后的值把位置让出来。带 `box-sizing: border-box` 和 1px 描边的容器，绝对定位的子元素相对内边距盒定位，整体比设计稿坐标偏 1px，核算时要算进去。

4. 排查手段：用 `miniprogram-automator` 的 `screenshot` 出模拟器截图，转成 BMP 后直接读像素坐标，和设计稿坐标逐项比。图形间距的实测值 ÷ SVG 里的值如果等于「取整后的盒高 ÷ viewBox 高」，就是这个原因。

## 相关链接

- 微信官方文档 · WXSS 尺寸单位：https://developers.weixin.qq.com/miniprogram/dev/framework/view/wxss.html
- MDN · preserveAspectRatio：https://developer.mozilla.org/en-US/docs/Web/SVG/Attribute/preserveAspectRatio
