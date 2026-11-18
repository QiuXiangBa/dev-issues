---
title: "打包 LibreOffice 导出中日文缺字 显式提供 Noto CJK 字体后恢复"
stack: "common"
platform: []
versions: ["Codex bundled runtime 26.1116.12010", "LibreOfficeDev 26.8.0.0.alpha0", "Python 3.12.14"]
tags: ["libreoffice", "headless", "docx", "cjk", "fonts", "fontconfig"]
project: "new-chat-6"
status: workaround
date: "2026-11-18"
---

## 现象

在 macOS 的打包无头 LibreOffice 环境中，用 python-docx 生成含中文、日文假名和罗马音的 DOCX，再经配套 `render_docx.py` 转成 PDF 与页面 PNG。

DOCX XML 中的文字完整，导出进程也成功退出，但渲染页上的中文和日文空白或变成方框，拉丁字母仍然显示。PDF 文本提取还出现重复的错误字符，不能靠“文本非空”判断成功。初始文档的东亚字体指定为系统可见的 `Hiragino Sans GB`。

本次实测 LibreOffice 构建为 `2c87e51eeaa2b413ff4ae097b2705eea1995d8e5`。上述现象只描述该打包环境的结果，不泛化为所有 macOS 或 LibreOffice 版本。

## 原因

桌面系统里存在一种字体，不等于隔离的无头渲染进程可以正确使用它。本次更换为显式提供的 Noto CJK OTF 字体，并固定任务级字体目录与缓存后，中日文及其 PDF 文本提取均恢复正常。

这是已验证的组合修复。没有分别隔离系统字体格式、字体缓存、`FONTCONFIG_FILE`、`SAL_FONTPATH` 或渲染器的用户目录设置，因此尚不能把其中某一项写成唯一根因，也不能断言只改一个环境变量就能修复。故本记录标记为 `workaround`。

## 解决方案

1. 从 Noto CJK 官方仓库取得 `NotoSansCJKsc-Regular.otf` 与 `NotoSansCJKsc-Bold.otf`，放入项目自己的持久字体目录。
2. 在 DOCX 的正文、标题和表格样式及必要的直接格式中，将东亚字体设为 `Noto Sans CJK SC`。用 python-docx 时同时处理 OOXML 的 `w:eastAsia`，不能只改拉丁字体名。
3. 创建任务级 `fonts.conf`，显式列出 CJK 字体的绝对路径、打包运行时的西文字体路径和可写缓存目录。
4. 运行原配套渲染器时显式传入 `FONTCONFIG_FILE` 与 `SAL_FONTPATH`，继续使用打包运行时的 Python 和 LibreOffice，不改用桌面安装的 LibreOffice。

下面均为占位路径，需替换成实际绝对路径；XML 路径中的特殊字符要按 XML 规则转义。

```xml
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <dir>/path/to/project/fonts</dir>
  <dir>/path/to/bundled/libreoffice/fonts/truetype</dir>
  <cachedir>/path/to/project/font-cache</cachedir>
  <alias>
    <family>Arial</family>
    <prefer><family>Noto Sans</family></prefer>
  </alias>
  <alias>
    <family>sans-serif</family>
    <prefer><family>Noto Sans CJK SC</family></prefer>
  </alias>
</fontconfig>
```

DOCX 样式或 run 的东亚字体设置示例：

```python
from docx.oxml.ns import qn

style.font.name = "Arial"
style.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")

run.font.name = "Arial"
run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
```

渲染命令示例：

```sh
FONTCONFIG_FILE="/path/to/project/fonts.conf" \
SAL_FONTPATH="/path/to/project/fonts" \
  /path/to/bundled/python3 /path/to/render_docx.py \
  /path/to/document.docx --output_dir /path/to/rendered --emit_pdf
```

若还需在同一台机器的编辑器中使用这些字体，可安装到用户字体目录。本次也执行了该步骤；它属于完整实测操作记录，但未单独证明它是渲染修复所必需。任务级字体配置使用绝对目录，避免只依赖渲染进程如何解释 `~` 或 `HOME`。

## 验证

- 重新导出并逐页查看 PNG，检查中文、假名、罗马音长音符、粗体及表格中是否仍有缺字、裁切或重叠。
- 提取 PDF 文本，与预期的真实短句比较，不能只检查字数或非空。
- 字体变化会影响字宽和分页，因此修复字体后重新检查整份文档。本次最终 13 页全部检查通过，单词注音和罗马音对齐正常。
- DOCX XML 内容完整、工具退出码为零、PDF 文件存在，都不能替代实际页面检查。

## 相关链接

- [Noto CJK 官方仓库](https://github.com/notofonts/noto-cjk)
- [简体中文 Sans OTF 字体目录](https://github.com/notofonts/noto-cjk/tree/main/Sans/OTF/SimplifiedChinese)

链接用于定位字体来源，不作为本次缺字根因已获上游确认的证据。
