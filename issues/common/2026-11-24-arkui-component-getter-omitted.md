---
title: "ArkUI 组件自定义 getter 在转译后缺失，系统返回键跳过弹层"
stack: common
platform: []
versions: ["DevEco Studio 26.0.0.851", "Hvigor 6.26.8", "HarmonyOS API 13 simulator", "HarmonyOS API 26 simulator"]
tags: [harmonyos, arkui, arkts, getter, transpilation, back-navigation]
project: arkui-navigation-example
status: workaround
date: "2026-11-24"
---

## 现象

页面用 `@State` 记录当前弹层，在 `@Entry @Component struct` 上定义自定义 getter 判断弹层是否打开。应用正常构建，弹层也能打开。此时按一次系统返回键，底层页面先退回首页，弹层仍盖在上面。点弹层自身的关闭按钮则正常。

## 原因

在上述工具链生成的入口组件类里，`onBackPress()` 仍然读取 `this.sheetVisible`，但类中缺少源码里的 `get sheetVisible()` 声明。运行时读取结果为 `undefined`，返回键处理便跳过关闭弹层的分支，继续执行页面导航。这个结论来自本次 V1 自定义组件的转译产物。

排查时，在模块的 `build` 目录中找到 `CompileArkTS` 生成的入口页面 `.ts` 文件，分别查找 getter 声明和调用处。只搜到属性名容易误判，因为读取表达式在故障版本中仍然存在。

## 解决方案

把派生判断改为普通实例方法，所有读取处都显式加上括号。下面保留了返回键处理的关键分支。

```ts
private sheetVisible(): boolean {
  return this.sheetKind !== SheetKind.Hidden;
}

onBackPress(): boolean {
  if (this.sheetVisible()) {
    this.sheetKind = SheetKind.Hidden;
    return true;
  }
  // 此处继续执行页面原有的返回逻辑。
  return false;
}
```

## 验证

修复后的转译文件中可以同时找到方法声明 `sheetVisible()` 和调用 `this.sheetVisible()`。从 Debug HAP 提取 `ets/modules.abc` 后反汇编，也能看到该方法定义和返回键处理对它的调用。

在 API 13 和 API 26 模拟器上打开弹层，按一次系统返回键，确认弹层消失且当前页面仍然可见。再按一次，确认页面执行原有的返回动作。两个断言分别检查弹层和底层导航，可以捕捉到弹层仍在、底层页面已经切换的情况。
