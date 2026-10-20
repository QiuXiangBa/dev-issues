---
title: "自定义 tabBar 盖在页面弹层之上，z-index 再大也盖不住"
stack: "wechat-mp"
platform: [wechat]
versions: ["微信开发者工具 基础库 3.17.3"]
tags: [custom-tab-bar, tabbar, z-index, overlay, bottom-sheet]
project: "xuejieai"
status: solved
date: "2026-10-05"
---

## 现象

`app.json` 里 `tabBar.custom: true`，用根目录 `custom-tab-bar/` 做了一个悬浮的底部导航（`position: fixed; z-index: 100`）。
Tab 页里做了一个全屏底部弹层（遮罩 + 面板，`position: fixed; z-index: 200`）。打开弹层后：

- 底部导航仍然浮在遮罩和面板**上面**，没有被遮罩压暗；
- 导航还能点，挡住了面板底部的内容。

把弹层的 z-index 调到 9999 也一样。

## 原因

自定义 tabBar 不和页面内容在同一个层叠上下文里，而是叠在页面之上的单独一层。页面元素的 `z-index` 只在页面内部比较，比不过它。
（结论来自微信开发者工具里的实测，机制本身官方文档没有写明；真机上没有单独验证过，表现应一致。）

## 解决方案

不和它比 z-index，而是让页面在打开弹层时**把自己的 tabBar 收起来**，关闭时再放回来。每个 Tab 页都有自己的 custom-tab-bar 实例，可以用 `page.getTabBar()` 拿到。

1. custom-tab-bar 加一个 `hidden` 状态：

```js
// custom-tab-bar/index.js
Component({
  data: { selected: -1, hidden: false },
  // ...
})
```

```html
<!-- custom-tab-bar/index.wxml -->
<view class="tab-bar {{hidden ? 'tab-bar--hidden' : ''}}">...</view>
```

```css
/* custom-tab-bar/index.wxss */
.tab-bar { transition: opacity 0.3s, transform 0.3s; }
.tab-bar--hidden { opacity: 0; transform: translateY(40rpx); pointer-events: none; }
```

2. 页面侧封装一个小函数，在弹层开 / 关时调：

```js
function setTabBarHidden(page, hidden) {
  const tabBar = typeof page.getTabBar === 'function' && page.getTabBar()
  if (tabBar) tabBar.setData({ hidden })
}

// 打开弹层
this.setData({ sheetShown: true })
setTabBarHidden(this, true)
// 关闭弹层
this.setData({ sheetShown: false })
setTabBarHidden(this, false)
```

`wx.hideTabBar()` / `wx.showTabBar()` 没有采用：自己控制的 `hidden` 状态能配合弹层动画淡出，也不依赖这两个接口在自定义 tabBar 下的表现。

## 相关链接

- 自定义 tabBar 文档：https://developers.weixin.qq.com/miniprogram/dev/framework/ability/custom-tabbar.html

## 更新 2026-10-20

### 保留导航的推荐方案：把模态弹层放进自定义 tabBar 宿主

上面的隐藏导航方案可以避开遮挡，但在底部面板开合时会出现「导航先消失、关闭后再出现」的跳变。如果产品需要导航留在原位、由遮罩压暗后被面板自然盖住，可以把弹层托管到 `custom-tab-bar` 内，让导航与弹层处于同一个渲染层。

这是开发者工具走查与项目验收得到的可用方案；不是对微信所有渲染器、客户端版本的层级机制保证。仍需在目标真机验证。

1. 在 `custom-tab-bar/index.json` 注册弹层组件。导航和弹层必须是兄弟节点：

```xml
<!-- custom-tab-bar/index.wxml -->
<view class="tab-bar {{hidden ? 'tab-bar--hidden' : ''}} {{modalVisible ? 'tab-bar--blocked' : ''}}">
  <!-- 原有导航内容 -->
</view>
<login-sheet id="login-sheet" bind:visibilitychange="onModalVisibilityChange" />
```

导航沿用 `position: fixed; z-index: 100`；弹层根容器用 `position: fixed; inset: 0; z-index: 500`，内部按遮罩、面板排列。不要把弹层放进导航的定位、裁剪或 transform 容器，否则会跟着导航隐藏、移动或被裁切。

2. 页面和嵌套组件优先通过当前页的 `getTabBar()` 找到宿主：

```js
const tabBar = typeof owner.getTabBar === 'function' && owner.getTabBar()
const sheet = (tabBar && tabBar.selectComponent('#login-sheet')) ||
  owner.selectComponent('#login-sheet')
sheet.open(reason, resume)
```

**保留本地回退组件**。非 Tab 路由、没有导航的单页模式（如从朋友圈进入）或宿主尚未就绪时，`getTabBar()` 可能不存在或返回空；如果同时删除本地声明，会出现 `null.open`。正常 Tab 路径只打开宿主弹层，不同时打开两份。

3. 登录模态打开期间不改变导航的 `hidden`、位置、透明度或选中项。由全屏遮罩覆盖并拦截背景点击，同时给导航加防护：

```js
onModalVisibilityChange(e) {
  this.setData({ modalVisible: e.detail.visible })
},
onTap(e) {
  if (this.data.hidden || this.data.modalVisible) return
  // 原来的切换逻辑
}
```

`.tab-bar--blocked { pointer-events: none; }` 只禁用导航自身；弹层是兄弟节点，仍然可操作。若父场景面板原本已经隐藏导航，关闭登录弹层也不应将其显示出来。

### 动画生命周期：先挂载、再展开，退场完成后才移除

- `visible` 控制挂载，`expanded` 控制 transform 和遮罩 opacity；挂载时面板为 `translateY(100%)`、遮罩为 `opacity: 0`。
- 在挂载的 `setData` 渲染 callback 后短暂等待（本例 50ms），再设置展开态。进场可用 350ms 减速曲线，退场可用 280ms；这些是实例参数，不是平台强制值。
- 关闭时保留节点，只将展开态撤销；等退场完成并确认卸载渲染后，才发出 `visibilitychange: false`、解除导航点击锁，并继续原业务操作。
- 定时器与渲染 callback 都检查同一轮次标记（如 `motionId`）。快速重开时取消旧退出；卸载时清理全部定时器和待恢复动作，旧 callback 不得关闭新弹层或提前解锁导航。
- 退场期间忽略迟到的授权回调，防止用户已取消后仍发起登录请求或恢复旧操作。
- 回归测试的 `setData` 桩要支持延迟 callback，覆盖「数据已 visible=false，但卸载 callback 还没执行就重开」的边界，不能只测同步 callback。

### 验证要点

开发者工具走查覆盖四个 Tab 和嵌套场景面板：弹层开合期间导航显隐、位置与选中项保持不变；点击锁持续到退出结束；快速开关 10 次、协议页往返保留弹层、取消后保留输入均通过。无导航宿主回退另有自动回归。

这次实现保留了父场景面板自身的导航隐藏逻辑，只让登录模态使用共享宿主；两类弹层各自管理状态，不互相覆盖。

参考：
- [Material 底部模态面板](https://m1.material.io/components/bottom-sheets.html#modal-bottom-sheets)
- [微信自定义 tabBar](https://developers.weixin.qq.com/miniprogram/dev/framework/ability/custom-tabbar.html)
