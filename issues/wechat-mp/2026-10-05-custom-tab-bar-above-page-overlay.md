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
