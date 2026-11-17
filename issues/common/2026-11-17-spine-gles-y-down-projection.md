---
title: "Spine C++ 骨骼接入 GLES 后上下倒置"
stack: "common"
platform: []
versions: ["spine-cpp 4.3", "OpenGL ES 3.0", "HarmonyOS 7.0.0.107 / API 26"]
tags: [spine, spine-cpp, opengl-es, projection, coordinates, y-down, harmonyos]
project: "native-rendering-example"
status: solved
date: "2026-11-17"
---

## 现象

将 spine-cpp 的 SkeletonRenderer 输出顶点直接交给 GLES，骨骼和动画都能解析、绘制，但角色上下倒置。调整容器位置或纹理 alpha 不能解决。

本次在 HarmonyOS API 26 模拟器实际复现，修正投影后正向显示。无需改动骨骼、图片或第三方 runtime 源码。

## 原因

本次使用的 spine-cpp 4.3 源码在 `Bone.cpp` 中初始化 `Bone::yDown = true`。输出坐标遵循该 runtime 的 Y-down 约定，而 GLES 裁剪空间的正 Y 朝上。

如果把两个轴都乘正缩放再送进裁剪空间，就没有处理 Y 轴方向差异。仅正确计算 FIT 缩放比例仍会得到倒置图像。

必须检查实际 vendored runtime 和业务是否覆盖过 yDown；不能假设所有 Spine 版本、后端或封装的默认方向都相同。

## 解决方案

在坐标约定转换处处理一次 Y 翻转。本例的骨骼输出是 Y-down、GLES 投影为 Y-up，按 setup pose bounds 做 FIT 并居中：

```cpp
// 前提：viewportWidth / viewportHeight 和 bounds 的宽高均为正。
const float fit = std::min(viewportWidth / boundsWidth,
                           viewportHeight / boundsHeight);
const float scaleX =  2.0f * fit / viewportWidth;
const float scaleY = -2.0f * fit / viewportHeight;
const float centerX = boundsX + boundsWidth  / 2.0f;
const float centerY = boundsY + boundsHeight / 2.0f;
```

这里各变量按浮点运算；顶点着色器使用相同的中心和缩放：

```glsl
vec2 clipPosition = (aPosition - uCenter) * uScale;
gl_Position = vec4(clipPosition, 0.0, 1.0);
```

- 负号修正的是几何顶点的坐标方向，不要同时翻 UV 或素材来“抵消”；那会掩盖契约并可能造成二次翻转。
- 若上游已经转换为 Y-up，就不应再使用负 scaleY。
- 翻转会改变三角形绕序；如果启用背面剔除，要相应核对。此例的二维渲染关闭 `GL_CULL_FACE`。
- 不为适配一个渲染后端去修改第三方 runtime 的默认值，避免影响共享该约定的其他计算。

### 回归与边界

- 使用上下明显不对称的骨骼，查看真实截图，而不是只检查“有渲染命令”或“构建成功”。
- 检查初始姿态、多种动作和视口尺寸改变后的 FIT/居中，确认没有双重翻转。
- 本次宿主机解析/渲染命令测试与 API 26 模拟器的多动作截图通过；未宣称在真机或其他 runtime 版本上复现。
- platform 暂为空数组；具体运行端和版本见 versions 与 `harmonyos` 标签。

## 相关链接

- [Spine 官方 runtimes：spine-cpp 4.3](https://github.com/EsotericSoftware/spine-runtimes/tree/4.3/spine-cpp)
- [Khronos OpenGL ES 3.0 规范](https://registry.khronos.org/OpenGL/specs/es/3.0/es_spec_3.0.pdf)
- [相关：XComponent 透明合成是独立问题](2026-11-17-xcomponent-egl-transparent-background.md)
