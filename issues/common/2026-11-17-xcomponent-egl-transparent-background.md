---
title: "XComponent 的 EGL 已透明清屏却仍显示黑色矩形背景"
stack: "common"
platform: []
versions: ["DevEco Studio 26.0.0", "HarmonyOS 7.0.0.107 / API 26", "OpenGL ES 3.0"]
tags: [harmonyos, arkts, xcomponent, egl, opengl-es, alpha, transparency]
project: "native-rendering-example"
status: solved
date: "2026-11-17"
---

## 现象

HarmonyOS ArkUI 的 `XComponentType.SURFACE` 用 EGL/GLES 绘制透明角色。EGL 已选择带 alpha 的配置，逐帧也执行 `glClearColor(0, 0, 0, 0)`，但角色所在矩形仍为黑色，无法透出父容器底色。

在 API 26 模拟器上实际观察到黑色矩形；补充 XComponent 背景设置后，透明区域能显示白色和浅蓝色两种父容器背景。

## 原因

透明合成涉及不同层：纹理像素、GLES framebuffer、EGL 窗口缓冲区，以及宿主 XComponent 的背景。

GLES 清屏 alpha 为 0，只说明绘制内容保留了透明区域；不等于宿主组件背景也透明。在本次环境中，未显式设置背景的 XComponent 显示黑底，仅修改 shader 或 EGL 配置不足以修复。

这与 straight-alpha / premultiplied-alpha 混用造成的边缘黑边不同，不能把整个矩形黑底一概归咎于图片。

## 解决方案

在创建 SURFACE XComponent 时显式设置透明背景：

```typescript
XComponent({ type: XComponentType.SURFACE, controller: this.controller })
  .backgroundColor(Color.Transparent)
  .width('100%')
  .height('100%')
```

同时保留底层透明链路：

1. EGL window config 使用 RGBA，例如 `EGL_ALPHA_SIZE = 8`，并检查配置选择成功。
2. 每帧透明清屏：

   ```cpp
   glClearColor(0.0f, 0.0f, 0.0f, 0.0f);
   glClear(GL_COLOR_BUFFER_BIT);
   ```

3. 像素表示与混合方式匹配。对于已经预乘的颜色，普通混合使用：

   ```cpp
   glEnable(GL_BLEND);
   glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
   ```

   不要对已预乘图片再预乘一次，也不要把该混合配置无条件用于 straight-alpha 数据。

### 回归与边界

- 至少切换两种明显不同的父容器底色，查看真实截图；透明空白区应透出底色，角色中的不透明白色部位仍应保持白色。
- 分别检查“整个矩形黑底”和“角色边缘黑边”，两者可能来自不同层。
- 验证组件整体卸载/重建后的透明合成。本次 API 26 模拟器的两种底色、组件重建及回前台均已检查通过。
- 没有真机 GPU、厂商合成器或所有 surface 强制丢失场景的验收；截图正常不代表帧率或功耗达标。
- 该记录为 HarmonyOS 问题；platform 暂用空数组，使用 `harmonyos` 标签检索，不将其标为已验 Android / iOS。

## 相关链接

- [HarmonyOS XComponent](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/ts-basic-components-xcomponent)
- [Khronos eglChooseConfig](https://registry.khronos.org/EGL/sdk/docs/man/html/eglChooseConfig.xhtml)
- [Khronos glBlendFunc](https://registry.khronos.org/OpenGL-Refpages/es3.0/html/glBlendFunc.xhtml)
- [相关：PixelMap 导出行距](2026-11-17-pixelmap-readback-packed-row-stride.md)
