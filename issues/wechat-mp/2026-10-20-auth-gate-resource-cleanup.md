---
title: "账号门禁拦截内部清理回调，导航失败后计时和音频仍运行"
stack: "wechat-mp"
platform: [wechat]
versions: ["微信开发者工具 Stable 2.02.2608060", "微信基础库 3.17.4", "Node.js 24.20.0"]
tags: [auth, lifecycle, cleanup, navigation, timer, audio, observer]
project: "wechat-miniprogram"
status: solved
date: "2026-10-20"
---

## 现象

统一页面门禁把所有 on 开头的方法都包装为“账号未就绪则直接返回”。计时页正在计时并播放音频，接口返回 401 后：

```text
门禁订阅先隐藏页面（accountReady=false）
→ 内部会话订阅调用 onAuthChanged
→ 包装器因账号未就绪而跳过回调
→ wx.reLaunch 跳转入口失败
→ 页面不可操作，但计时器和音频继续运行
```

复现时观察到页面已隐藏、导航失败，但音频仍在播放、计时器仍存在、页面阶段仍为 running。

## 原因

1. 用方法名前缀识别用户事件，把内部会话观察回调也拦截了。onAuthChanged 原本负责取消旧会话计时、停止音频并清空上下文。
2. 门禁订阅先把账号状态改为不可用，后执行的清理订阅恰好被这一状态挡住。
3. 资源清理只依赖正常的 onHide/onUnload。跳转失败时原页面未退出，不能指望导航一定带来这些生命周期回调。
4. 只隐藏 WXML 或禁用交互，不会停止逻辑层定时器、音频或其他订阅。

## 解决方案

把需要授权的用户操作与必须执行的失效处理、生命周期清理分开管理。

- 对点击、提交、分享等用户操作实施门禁。
- 内部会话失效回调继续执行，不因 accountReady=false 而跳过。若保留现有 on 前缀包装器，应明确排除 onAuthChanged 等内部回调。
- 阻止业务页面时，在尝试 wx.reLaunch 之前主动暂停或释放资源，不能等待导航成功。也可以复用原始 onHide 实现进行暂停，但应直接调用原实现，避免再经过门禁包装。
- 随后的会话失效处理应清空旧账号会话上下文，保证恢复后不会继续旧计时或把旧记录提交给新账号。
- onHide/onUnload 中仍保留清理；清理函数要可重复调用，避免主动失效处理与生命周期再次清理发生冲突。
- 页面卸载时解除门禁订阅及业务会话订阅。

示意实现（资源清理方法由具体页面提供）：

```js
function blockPage(page) {
  page.setData({ accountReady: false })
  page.releaseAccountResources()
  // 即使跳转失败，资源也已经停止。
  wx.reLaunch({
    url: '/pages/login/index',
    fail: () => page.showAccountEntryError(),
  })
}

function onAuthChanged() {
  // 内部失效回调必须继续执行，不能套“账号未就绪就返回”的门禁。
  if (!isCurrentSessionValid()) {
    this.releaseAccountResources()
    this.clearOldSessionContext()
  }
}
```

此处“账号失效”与正常切后台应分别处理：正常后台暂停可以保留计时上下文，账号失效则必须防止旧账号任务被恢复或跨账号上报。

## 验证

回归测试加载实际计时页面配置、会话订阅和请求封装，仅模拟微信 API 及接口响应：

1. 开始计时并选择可播放的音频，确认计时器存在且音频正在播放。
2. 将开始记录请求回调设为 401，再调用 wx.reLaunch 的 fail 回调；不主动调用 onHide/onUnload。
3. 断言页面已隐藏、音频停止、计时器已清空、旧会话上下文已释放，页面回到空闲状态。
4. 推进模拟时钟，读数不再变化。
5. 完成静默恢复，旧页面不重新启动资源，也不向新账号提交旧记录。
6. 再执行 onHide/onUnload，清理可重复运行，卸载后不会继续响应会话订阅。

这是应用层回归验证，导航失败由测试主动注入；不表示在真机上发现了微信平台必然出现的导航故障。

## 相关记录

- [账号恢复失败后的导航循环](2026-10-20-auth-recovery-navigation-loop.md)
