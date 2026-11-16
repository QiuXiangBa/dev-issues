---
title: "Magpie 自动填写密钥后获取模型报 401：真实粘贴同步输入状态"
stack: "ai-tools"
platform: []
versions: ["Magpie 0.1.4291", "macOS 26.6.2", "Sub2API 0.2.21"]
tags: ["magpie", "codex", "cua", "macos", "wails", "webview", "input-events", "api-key", "http-401"]
project: "github-claude"
status: "workaround"
date: "2026-11-16"
---

## 现象

通过 Codex CUA 操作 macOS Magpie，在「供应商 → 自定义供应商」中接入自建中转，选择 OpenAI Responses，填写兼容地址，例如 `https://relay.example.com/v1`。

使用原生应用自动化的 `setValue` 填写密钥后，Wails WebView 中的密码框已显示圆点，但点击「获取模型」返回：

```text
401 Unauthorized (API key is required in Authorization header (Bearer scheme), x-api-key header, or x-goog-api-key header)
```

随后使用同一个已授权密钥，通过真实粘贴重新输入，再次获取模型成功；没有更换密钥或关闭 TLS 证书校验。

## 原因

Magpie 0.1.4291 的供应商编辑器中：

1. 普通单密钥输入通过密钥框的 `input` 事件处理器把输入值同步到 `draft.key`。
2. 「获取模型」通过 `asTyped()` 读取 `draft.key`，以 `key` 字段交给 `provider/list`，没有直接读取密码框当前可见值。
3. 这条密钥同步路径没有依赖 `blur` 的赋值逻辑。

本次「AX 设值后可见圆点，但请求提示缺少密钥；真实粘贴后成功」的现象，与输入事件未同步应用内部状态一致。没有直接采集该次 JavaScript 事件或出站请求头，因此这是结合源码的原因推断，不应推广为所有 AX `setValue`、所有输入框或所有版本都不触发 `input`。

## 解决方案

1. 遇到明确的「缺少认证头」提示时，先检查自动化输入是否进入应用状态。界面显示圆点只能证明密码框有可见值，不能证明后续请求使用了它。

2. 从新读取的 AX 状态定位密钥框，点击后用真实键盘输入或原生粘贴重新填写。例如，已有应用句柄 `app`、当前字段索引 `keyFieldIndex`，且 `apiKey` 已从获授权的来源取得时：

   ```javascript
   await app.click(keyFieldIndex);
   await app.pressKey("super+a");
   await app.paste(apiKey);
   await app.pressKey("Tab");
   await app.getAXState();
   ```

   本次采用了上述全选、粘贴、离焦流程。关键是真实输入或粘贴触发状态同步；`Tab` 是离焦收尾操作，不能单独当作修复。不要在日志、AX 输出或截图中暴露密钥明文。

3. 再次点击「获取模型」，等待界面返回模型列表。每次界面更新后重新读取 AX 状态，再决定下一步；不要沿用已经失效的元素索引。

4. 保存供应商，再用模型编辑页的「测试模型」或单模型右键测试，验证实际推理请求。只有列表请求通过时，验证范围还只是模型发现与鉴权。

5. 若真实输入后仍失败，按实际报错继续区分「缺少认证头」「密钥无效」「余额或订阅不足」及 TLS/网络错误，再检查相应环节。

## 验证结果与范围

- 本次界面返回 20 个模型；这是当前上游和分组的结果，不是通用成功数量。
- 保存后，`gpt-6-luna` 与 `gpt-6.1-sol` 的 Responses 请求均成功，界面显示分别约 1.9 秒和 2.6 秒内响应。
- 验证范围为 Magpie → 自建中转 → 上游模型；Agent 客户端接入另行验证。
- 这是自动化交互方式的规避方案，没有修改 Magpie 源码。

## 相关链接

- [Magpie 0.1.4291：密钥输入事件更新 draft.key](https://github.com/yetone/magpie/blob/v0.1.4291/internal/gui/assets/app.js#L9463-L9507)
- [Magpie 0.1.4291：asTyped 读取 draft.key](https://github.com/yetone/magpie/blob/v0.1.4291/internal/gui/assets/app.js#L7810-L7814)
- [Magpie 0.1.4291：获取模型调用 provider/list](https://github.com/yetone/magpie/blob/v0.1.4291/internal/gui/assets/app.js#L10746-L10754)
