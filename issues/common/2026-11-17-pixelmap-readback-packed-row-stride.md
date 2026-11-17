---
title: "PixelMap 读回 RGBA 时混用内部 stride 导致缓冲区布局不一致"
stack: "common"
platform: []
versions: ["DevEco Studio 26.0.0", "HarmonyOS 7.0.0.107 / API 26", "OpenGL ES 3.0"]
tags: [harmonyos, arkts, imagekit, pixelmap, stride, rgba, opengl-es]
project: "native-rendering-example"
status: solved
date: "2026-11-17"
---

## 现象

适用链路：HarmonyOS ImageKit 将 PNG 解码为 `RGBA_8888` PixelMap，经 `readPixelsToBuffer` 读到 ArrayBuffer，再交给 native 渲染器上传纹理。

读回 buffer 按紧凑像素分配，但 native 收到的行距却来自 `ImageInfo.stride` 等内部存储信息。当内部行距大于 `width * 4`，native 按该 stride 逐行读取时，会出现长度校验失败或读错行的风险；没有边界校验时还可能越界。

本问题来自源码契约审查：不把风险描述为所有解码器均已复现的异常，也没有可通用引用的原始错误码。修复后的实际读回、上传与显示已在 API 26 模拟器跑通。

## 原因

PixelMap 的内部对齐布局与导出 buffer 的布局不是同一个概念。这里的 `readPixelsToBuffer` 导出紧凑 RGBA 数据；内部 stride 不能原样作为紧凑 buffer 的逐行步长。

对于宽 `w`、高 `h` 的 RGBA_8888：

- 紧凑行距为 `rowBytes = w * 4`，buffer 为 `rowBytes * h` 字节。
- 若 native 使用步长 `stride`，最少可读长度为 `stride * (h - 1) + rowBytes`。
- 当 `h > 1` 且 `stride > rowBytes`，上述最少长度大于紧凑 buffer 的长度，生产方和消费方的契约已经不一致。

只调 `GL_UNPACK_ALIGNMENT` 不能修复此前 CPU 侧已经发生的错误寻址。

## 解决方案

明确格式和导出布局，再把同一份布局信息传给 native。以下片段的前提是 PixelMap 已按 `desiredPixelFormat: image.PixelMapFormat.RGBA_8888` 解码：

```typescript
const info = await pixelMap.getImageInfo();
const rowBytes = info.size.width * 4;
const pixels = new ArrayBuffer(rowBytes * info.size.height);
await pixelMap.readPixelsToBuffer(pixels);
// 向 native 传 width、height、rowBytes 与 pixels；
// 不传 PixelMap 内部存储的 stride。
```

- 不要把这套 `width * 4` 公式照搬到 RGB、YUV、多平面像素或另一个读回 API。
- native 保留 buffer 长度校验；若另一路输入确实有 padding，按它真实的 stride 逐行拷贝成紧凑数据。
- alpha 是否已预乘是另一个维度：根据 `alphaType` 处理，不能靠修改 stride 解决黑边。
- 异步解码/读回期间组件可能被销毁；在分配与交付前检查取消状态，并在 finally 释放 PixelMap / ImageSource。

### 回归与边界

- 使用带透明区、可区分上下行颜色的测试 PNG，至少覆盖一种不容易满足内部对齐的宽度；记录格式、尺寸、导出长度与传给 native 的步长。
- native 小图测试分别覆盖 straight-alpha 预乘、紧凑 premultiplied 直接复制、带 padding 的 premultiplied 逐行复制，检查 padding 不进入输出。
- 本次上述 native 测试及 API 26 模拟器的真实纹理渲染通过；未测试其他厂商解码器和鸿蒙真机，不据此推广到所有像素格式或系统版本。
- 当前知识库的 platform 枚举未包含 HarmonyOS，因此使用空数组；以 `harmonyos` 标签和 versions 检索，不冒填为 Android。

## 相关链接

- [HarmonyOS PixelMap API](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/arkts-apis-image-pixelmap)
- [Khronos glPixelStorei](https://registry.khronos.org/OpenGL-Refpages/es3.0/html/glPixelStorei.xhtml)
- [相关：XComponent 透明背景](2026-11-17-xcomponent-egl-transparent-background.md)
