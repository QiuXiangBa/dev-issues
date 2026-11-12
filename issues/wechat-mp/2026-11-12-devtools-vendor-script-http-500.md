---
title: "开发者工具基础库清单获取失败，WAServiceMainContext.js 加载返回 500"
stack: "wechat-mp"
platform: [wechat]
versions: ["macOS", "微信开发者工具 2.02.2608060", "微信基础库 3.17.5（失败时实际加载）", "微信基础库 3.17.3（恢复后验证）"]
tags: [devtools, sdk, initialization, http-500, authentication, metadata, cache, signature]
project: "miniapp"
status: solved
date: "2026-11-12"
---

## 现象

开发者工具启动原生小程序时，本地基础库脚本请求返回 HTTP 500：

```text
Failed to load resource: the server responded with a status of 500 (Internal Server Error)
http://127.0.0.1:<port>/__dev__/WAServiceMainContext.js?t=wechat&v=3.17.5
(env: macOS,mp,2.02.2608060; lib: 3.17.5)
```

`<port>` 是当前工程窗口使用的临时端口。随后可能出现同一资源被 preload、但未使用的警告。

两份工程配置 `project.config.json` 和 `project.private.config.json` 当时都已固定 `libVersion: "3.17.3"`，实际失败请求却使用 3.17.5；只读配置不足以判断真正运行的版本。

## 原因

同一次启动日志确认了直接故障链，以下仅保留错误摘要：

```text
getUsageRateList failed: Error: 需要重新登录
getVendorConfig: getOnlineConfig failed, using fallback Error: 需要重新登录
config missing or md5 empty: version=3.17.5, libInfo=undefined
onProxyError /__dev__/WAServiceMainContext.js Error: WAServiceMainContext.js not found in vendor contents map
onProxyError /__dev__/WAServiceMainContext.js 500
```

1. 开发者工具自身的登录凭证异常，导致线上基础库清单获取失败，加载器转用回退清单。
2. 回退清单缺少所需版本的校验元数据。加载器无法取得可接受的基础库包，因而没有向内容映射表提供主脚本。
3. `VendorService.getFile` 抛出上述异常，本地代理捕获后转换成 HTTP 500。本次失败发生在基础库脚本内容供应阶段。

安装代码与日志相符：下载目录中的包需要已验证状态或有效签名元数据才能使用；磁盘上存在 `.wxvpkg` 不等于加载器能够接受它。`does not exists online` 在此也可能由版本元数据缺失触发，不能据此断言官方不存在该版本。

后续日志显示，线上清单恢复后，旧 3.17.5 包又出现 `verify md5 error`，随后重新下载并报告 `download and verify success`。这是后续发现的校验问题，不能倒推为最初 500 的唯一原因；该加载路径包含签名验证，不能只按日志名称理解为一次普通 MD5 比较。

仍未确定的部分：

- 开发者工具登录凭证异常的起因，以及旧包校验失败的来源。
- 最初为何从已配置的 3.17.3 走到 3.17.5。代码支持“固定版本不在清单中时回退到列表首项”的解释，但未完整追踪当次最初的输入值。

这些证据不足以证明 3.17.5 存在兼容性缺陷，也不同于基础库执行后的 PageTypeById 初始化异常。

## 解决方案

1. **先核对实际版本和同次失败日志。** 使用控制台报错末尾的 `lib`、启动日志，或官方自动化接口交叉核对：

   ```js
   await miniProgram.send('Tool.getInfo')
   // 本次恢复后实测：{ version: '2.02.2608060', SDKVersion: '3.17.3' }
   ```

   开发者工具日志通常位于 `~/Library/Application Support/微信开发者工具/<实例目录>/WeappLog/logs/`。按工程路径、时间和端口定位同一次启动，重点查 `getOnlineConfig`、`需要重新登录`、`config missing or md5 empty` 和 `not found in vendor contents map`。

2. **若仍提示需要重新登录，先恢复开发者工具自身的登录会话，再等待清单与基础库包准备完成。** 这是开发者工具登录，不是小程序业务账号登录。关注清单成功加载、包下载和校验成功的日志，而不是反复改业务代码。本例观察到清单恢复、旧包校验失败及重新下载成功；没有单独验证“只重新登录”就足以修复所有同类故障。

3. **重新打开工程，并核对实际加载版本。** 本例保留原有两份配置中的已验证调试基线 3.17.3，通过官方 CLI 重新打开主工程后恢复运行：

   ```bash
   /Applications/wechatwebdevtools.app/Contents/MacOS/cli open --project /path/to/miniprogram
   ```

   如需选择基线，在“详情 → 本地设置”选择团队已验证的版本；只调整对应字段并保留其他本地偏好。元数据仍缺失时，重写一次 `libVersion` 可能继续触发回退，因此必须再查实际 `SDKVersion`。

4. **用真实界面验证恢复。** 检查首屏实际出现、启动覆盖层结束，切换一个代表性 Tab 后返回，并观察运行时异常。若通过 Network 核对脚本请求，使用当前窗口的地址和端口，检查响应状态、类型与非空脚本内容；旧端口可能已经失效。

不要为了上述错误清空整个开发者工具用户数据目录。基础库缓存 `WeappVendor` 在同一工具实例下供多个工程使用；模拟器账号和业务存储属于其他区域。当前清单、包和运行已经恢复时，无需继续删除缓存或修改 SDK 源码。

## 验证与限制

- 恢复后的 `Tool.getInfo` 确认开发者工具 2.02.2608060、SDKVersion 3.17.3；两份工程配置仍为 3.17.3。
- 已查看首页、另一 Tab 及返回首页后的真实模拟器截图，页面正常；切换观察期间运行时异常为 0、控制台 error 计数为 0。该计数不覆盖接入观察前的全部启动日志。
- 只读复核确认当前 3.17.3 和 3.17.5 包均包含主脚本，并通过当前清单与安装公钥对应的签名验证；旧包已经替换，无法再据当前包推断旧包为何校验失败。
- 外部直接请求原端口和后续端口均超时，没有取得可检查的响应正文。原 HTTP 500 有明确服务日志证据；当前恢复由实际版本、可见界面和页面切换验证，不声称直接 HTTP 探测已得到 200，也不能凭超时认定服务卡死。
- 未改业务代码、未清空账号或业务缓存，未做真机测试。状态 solved 表示本机运行已恢复，不代表修复了 SDK 内部缺陷或保证永不复发。
- preload 未使用警告不能作为本次 500 的根因证据。历史正常启动时也曾存在该警告，无需因此单独修改 `as`、启动动画或业务初始化。

## 相关链接

- [开发者工具灰度基础库启动报 PageTypeById undefined](2026-10-21-gray-sdk-page-type-initialization.md)：同工具版本的另一类故障，发生在脚本执行阶段，不应与本例混为同一根因。
- [微信开发者工具命令行文档](https://developers.weixin.qq.com/miniprogram/dev/devtools/cli.html)

本条依据本机服务日志、已安装工具的基础库加载与代理实现，以及恢复后的真实运行验证整理；未附原始日志或项目私有链接。
