---
title: "HarmonyOS 部分 SVG 图形在模拟器中缺失：离线转透明 PNG 规避"
stack: "common"
platform: []
versions: ["HarmonyOS API 13 simulator", "HarmonyOS API 26 simulator", "HarmonyOS SDK 26.0.0.105"]
tags: [harmonyos, arkts, arkui, svg, image, rasterization, visual-testing]
project: "ui-rendering-example"
status: workaround
date: "2026-11-20"
---

## 现象

ArkUI `Image` 加载安装包内的 SVG 图标时，在所测 API 26 模拟器中，一份组合图标的实心圆未显示，其他部分仍可见；同一图标在所测 API 13 模拟器中显示完整。

原 SVG 包含普通 `path`、`circle`、`rect`，以及分组和平移。页面能正常运行，相关控件存在且可点击，自动化状态断言也能通过；实际查看截图才发现图形不完整。

将相关图标离线导出为透明 PNG，保持原逻辑显示尺寸后，两台模拟器均显示完整。

## 原因

已确认的是**本次资源在两个模拟器环境中的显示差异**，尚未定位解析器或渲染器的具体原因。

- 不能仅因原文件使用了 `circle`、描边或分组，就认定某个 SVG 标签、GPU 或全部 API 26 设备存在缺陷。
- SDK 声明支持 SVG；不能把这次现象表述为「HarmonyOS 不支持 SVG」。
- 未验证更换 SVG 写法或切换增强解析选项的效果，因此不将其列为已证实修复。
- PNG 方案绕过了原有 SVG 显示路径，但不代表框架缺陷已经被修复，所以状态为 `workaround`。

## 解决方案

### 1. 先确认问题范围

使用相同资源和明确的逻辑尺寸，在目标 API 版本上分别截图。检查图标整体、局部填充、描边和透明边缘，不只检查控件树、点击事件或页面是否崩溃。

尽量用最小页面排除遮挡、裁切、透明度及着色配置影响；没有完成原因隔离时，应保留「底层原因未确认」的结论。

### 2. 将受影响的静态图标离线光栅化

用能正确显示原 SVG 的本地导出工具或浏览器生成透明 RGBA PNG，再将产物作为普通图片资源打包。无需在应用运行时解析、转换或下载图标，也无需增加运行时依赖。

例如，显示尺寸为 `22 × 22vp` 的小图标可导出为 `66 × 66px`，页面仍按 `22 × 22vp` 显示。本次采用 3× 像素尺寸；这不是平台强制要求，应按实际密度、清晰度和包体积选择倍率。

本地浏览器 Canvas 的核心转换步骤如下（示意代码，`svgText` 来自本地文件，不上传到在线转换服务）：

```javascript
async function rasterizeSvg(svgText, widthVp, heightVp, scale = 3) {
  const url = URL.createObjectURL(
    new Blob([svgText], { type: 'image/svg+xml' })
  );
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(widthVp * scale);
    canvas.height = Math.round(heightVp * scale);
    // 不铺底色，保留透明背景。
    canvas.getContext('2d').drawImage(
      image, 0, 0, canvas.width, canvas.height
    );
    return canvas.toDataURL('image/png');
  } finally {
    URL.revokeObjectURL(url);
  }
}
```

输入 SVG 需自包含，具有明确尺寸或 `viewBox`；若依赖外部图片、字体或样式，先处理这些依赖并核对导出结果。不要只改文件扩展名冒充格式转换。

替换资源时保持逻辑资源名和布局尺寸稳定，并确保同一资源目录不会留下同名 SVG/PNG 歧义。需要多尺寸缩放或动态改色的图标，应先评估光栅化的取舍，不必将所有 SVG 一律转换。

### 3. 重新安装并做视觉验收

- 使用包含 PNG 的最终安装包，在原本正常和异常的两个 API 版本上重新验证。
- 检查整图及局部形状、透明边缘、显示尺寸和清晰度；记录实际系统版本和包版本，避免看错旧包或旧截图。
- 保留原功能回归，并增加截图复核。控件存在或点击通过，不能证明图形完整。

本次最终包在 API 13、API 26 模拟器上均确认图形完整；未据此宣称所有真机或其他系统版本均通过。

## 相关链接

无可对应的公开缺陷链接。本文记录本地对照测试与资源格式规避，不附原业务素材、截图或私有日志。
