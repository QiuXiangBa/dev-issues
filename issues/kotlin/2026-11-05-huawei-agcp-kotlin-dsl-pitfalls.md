---
title: "华为 AGC 插件 agcp 接入 Kotlin DSL 安卓工程：版本不兼容、配置缓存报错、json 缺包名"
stack: "kotlin"
platform: [android]
versions: [agcp 1.9.6.300, agconnect-core 1.9.6.300, agp 8.11.1, gradle 8.14.3, kotlin 2.1.20]
tags: [huawei, agconnect, agcp, gradle, configuration-cache, kotlin-dsl, version-catalog, r8, resource-shrinking]
project: "tutuai"
status: workaround
date: "2026-11-05"
---

## 现象

按 AppGallery Connect 控制台「集成 SDK」向导接 `com.huawei.agconnect` 插件和 `agconnect-core`。工程用的是 Kotlin DSL、版本目录、`settings.gradle.kts` 集中声明仓库（`FAIL_ON_PROJECT_REPOS`），AGP 用 `plugins {}` 声明。依次撞到四个问题：

1. 照控制台示例用 agcp 1.5.2.300，配置阶段失败：

   ```
   A problem occurred configuring project ':app'.
   > com.android.tools.build:gradle is no set in the build.gradle file
   ```

2. 换成 1.9.6.300 后，开着 Gradle 配置缓存（`org.gradle.configuration-cache=true`）时清单任务失败：

   ```
   Execution failed for task ':app:processDebugManifest'.
   > Could not find method getMetadataByConfig() for arguments [] on task ':app:processDebugManifest' of type com.android.build.gradle.tasks.ProcessMultiApkApplicationManifest.
   ```

3. 插件校验 json 失败：

   ```
   Execution failed for task ':app:processDebugAGCPlugin'.
   > ERROR: Failed to verify AGConnect-Config '/client/package_name', expected: 'com.example.app', but was: ''
   ```

4. 开了 `isShrinkResources = true` 的 release 包里，插件生成的 `agc_*` 字符串一条都没剩（debug 包里有几十条）。

## 原因

1. agcp 1.5.x 要在根工程 `buildscript` 的 classpath 里找 `com.android.tools.build:gradle` 来判断 AGP 版本，用 `plugins {}` / 版本目录声明 AGP 时找不到。另外华为 Maven 仓库**没有发布插件标记**（`com.huawei.agconnect.gradle.plugin` 404），`plugins { id("com.huawei.agconnect") }` 默认解析不到。
2. agcp 在 `processXxxManifest` 任务上挂了一个 Groovy 闭包，闭包里回调插件对象自己的方法 `getMetadataByConfig()`。配置缓存序列化任务时不会带上闭包的 owner（插件对象），反序列化后方法查找落到任务上，所以找不到。用 `--no-configuration-cache` 跑一次就能确认是这个原因。
3. 在 AGC 里**还没给应用设置包名**时下载的 `agconnect-services.json`，`client`、`app_info`、`appInfos[]` 里都没有 `package_name`。插件要求它等于 `applicationId`。
4. 插件把 json 加密成 `agc_<sha256>` 字符串资源，SDK 运行时用 `"agc_"` 前缀拼出名字再调 `getIdentifier` 查。资源收缩默认的 safe 模式只在保留下来的代码里看到这个前缀常量时才保留这些资源。如果 App 里还没有代码读 AGC 配置（启动时 `AGConnectInitializeProvider` 只做初始化，不读配置），读配置的那段代码会被 R8 删掉，资源也跟着被删。`mapping/release/resources.txt` 里能看到 `string/agc_... : reachable=false`。

## 解决方案

1. **用新版 agcp**（1.9.6.300 可以搭配 AGP 8.11 和 `plugins {}` 写法），插件在 `pluginManagement` 里按坐标解析：

   ```kotlin
   // settings.gradle.kts
   pluginManagement {
       repositories {
           google()
           mavenCentral()
           gradlePluginPortal()
           maven("https://developer.huawei.com/repo/") {
               content { includeGroupByRegex("com\\.huawei.*") }
           }
       }
       resolutionStrategy {
           eachPlugin {
               // 华为仓库没有发布插件标记，按坐标找插件本体
               if (requested.id.id == "com.huawei.agconnect") {
                   useModule("com.huawei.agconnect:agcp:${requested.version}")
               }
           }
       }
   }
   dependencyResolutionManagement {
       repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
       repositories {
           google()
           mavenCentral()
           maven("https://developer.huawei.com/repo/") {
               content { includeGroupByRegex("com\\.huawei.*") }
           }
       }
   }
   ```

   ```toml
   # gradle/libs.versions.toml
   [versions]
   agconnect = "1.9.6.300"
   [libraries]
   huawei-agconnect-core = { group = "com.huawei.agconnect", name = "agconnect-core", version.ref = "agconnect" }
   [plugins]
   huawei-agconnect = { id = "com.huawei.agconnect", version.ref = "agconnect" }
   ```

   根 `build.gradle.kts` 写 `alias(libs.plugins.huawei.agconnect) apply false`；app 模块写 `alias(libs.plugins.huawei.agconnect)`，再加 `implementation(libs.huawei.agconnect.core)`。注意：`pluginManagement {}` 是单独编译的，引用不到 settings 脚本里定义的函数，华为仓库只能在两处分别写出来。

2. **关掉配置缓存**（目前只能这样绕过）：`gradle.properties` 里设 `org.gradle.configuration-cache=false`，写注释说明原因。构建缓存 `org.gradle.caching` 不受影响。以后升级 agcp 时可以试着重新打开。

3. **在 AGC 控制台给应用设置包名，然后重新下载 json**。不要手动往文件里补包名：控制台上没有绑定包名，依赖包名的服务端能力不会生效。在等新文件期间，可以用一份临时补了包名的副本验证构建，但不要提交。

4. **release 资源不用额外配保留规则**：实测只要有代码读配置（比如 `AGConnectInstance.getInstance().options.getString("client/app_id")`），资源收缩就会自动保留全部 `agc_*`。接入具体的华为能力后，用 release 包临时打一行日志，确认能读到 `app_id`。做对照实验时要注意：加日志本身就会让资源被保留，所以「去掉保留规则再加日志验证」证明不了保留规则没用。要看「没有日志也没有保留规则」时启动日志里有没有 `ResourcesUtils` 报 `resId == 0`。

其他：

- `agconnect-core` 自带 consumer ProGuard 规则（`-keepnames class com.huawei.agconnect.**` 等），不用自己加 `-keep`。
- 合并后的清单会多出 `AGConnectInitializeProvider`、`ServiceDiscovery` 和 meta-data `com.huawei.hms.client.appid`。
- json 里有 `client_secret`、`api_key`，但插件会把它们写进资源、随每个 APK 分发，缺了这个文件构建直接失败。多数团队把它入库；如果项目规定「密钥不入库」，需要明确定一个例外，否则每个新 worktree 都构建不了。

## 相关链接

- 华为 Maven 仓库 agcp 版本列表：https://developer.huawei.com/repo/com/huawei/agconnect/agcp/maven-metadata.xml
- Gradle 配置缓存要求：https://docs.gradle.org/current/userguide/configuration_cache.html
- 安卓资源收缩与 safe 模式：https://developer.android.com/build/shrink-code#keep-resources
