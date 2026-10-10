# 索引

由 `scripts/index.sh` 自动生成，不要手改。共 29 条。

## ai-tools

| 状态 | 日期 | 标题 | 端 | 标签 |
|---|---|---|---|---|
| solved | 2026-09-29 | [Figma 导出 SVG 的硬投影滤镜（hardAlpha + feOffset）光栅化后边缘锯齿：改画实体偏移副本](issues/ai-tools/2026-09-29-figma-svg-drop-shadow-filter-aliased-edges.md) | ios, web | figma, svg, drop-shadow, filter, svg-rasterize, wkwebview, antialiasing, design-to-code |
| solved | 2026-09-16 | [Figma 旋转存储的画板：多层 SVG 素材用 JSX 转 HTML 整页反旋转后 WKWebView 光栅化](issues/ai-tools/2026-09-16-figma-rotated-artboard-svg-assets-via-html.md) | ios, web | figma, mcp, design-to-code, svg-rasterize, wkwebview, tailwind, rotated-artboard, claude-code |
| solved | 2026-09-16 | [Figma 云端 MCP 未授权时改走桌面端 Dev Mode 本地 MCP 读设计稿](issues/ai-tools/2026-09-16-figma-mcp-unauthorized-use-desktop-dev-mode.md) | ios, web | figma, mcp, oauth, design-to-code, claude-code, json-rpc, svg-rasterize |
| solved | 2026-09-08 | [流式调用下 tool&#95;use 的 input 解析失败](issues/ai-tools/2026-09-08-tool-use-json-truncated.md) | backend | claude-api, tool-use, streaming, json-parse, max-tokens |

## common

| 状态 | 日期 | 标题 | 端 | 标签 |
|---|---|---|---|---|
| solved | 2026-09-28 | [飞书自建应用换 App ID 后 CLI 全线 99991672 / 91403 / open&#95;id cross app：scope、open&#95;id、资源授权都按应用隔离](issues/common/2026-09-28-feishu-app-switch-breaks-scopes-openid-resources.md) | backend | feishu, lark, permission, scope, open-id, app-id, bitable, calendar, drive, lark-cli |
| solved | 2026-09-21 | [飞书开放平台按邮箱给个人账号授权文档返回 1063001，需按手机号换 open&#95;id](issues/common/2026-09-21-feishu-share-email-invalid-use-openid.md) | backend | feishu, lark, permission, open-id, tenant-access-token, bitable, docx |
| solved | 2026-09-08 | [zsh 中 echo ====X==== 分隔横幅触发 =cmd 展开并中断整条命令](issues/common/2026-09-08-zsh-echo-equals-banner-not-found.md) |  | zsh, shell, claude-code, echo, equals-expansion |

## kotlin

| 状态 | 日期 | 标题 | 端 | 标签 |
|---|---|---|---|---|
| solved | 2026-10-10 | [腾讯智聆口语评测 Android SDK 自定义数据源回放整段 PCM 时与建连竞态，音频被静默丢弃导致超时](issues/kotlin/2026-10-10-tencent-soe-buffer-source-race.md) | android | tencent-cloud, soe, speech-evaluation, websocket, okhttp, race-condition, audio, timeout |
| solved | 2026-10-10 | [OkHttp WebSocket 服务端先关连接时只回调 onClosing，只在 onClosed 里收尾会一直挂到超时](issues/kotlin/2026-10-10-okhttp-websocket-peer-close-no-onclosed.md) | android, backend | okhttp, websocket, close-frame, callback, timeout, hang |
| solved | 2026-10-09 | [Android SoundPool 播长音效被截掉结尾（单段解码上限约 1MB）](issues/kotlin/2026-10-09-soundpool-long-sample-truncated.md) | android | android, soundpool, mediaplayer, audio, sound-effect, truncation |
| solved | 2026-10-06 | [Compose AnimatedContent 不向外转发子项的文字基线：旁边 alignByBaseline 的单位在内容更新后跳到数字顶边](issues/kotlin/2026-10-06-compose-animatedcontent-drops-baseline.md) | android | compose, animatedcontent, baseline, alignbybaseline, alignment-line, firstbaseline, text, animation |
| solved | 2026-10-05 | [Compose 照抄 SwiftUI 文字框左上角坐标，字会偏下：按首行基线对齐](issues/kotlin/2026-10-05-compose-text-baseline-match-swiftui.md) | android, ios | compose, swiftui, text, baseline, line-height, port, fixed-canvas, typography |
| solved | 2026-09-18 | [Compose ModalBottomSheet 是独立窗口，会盖住 Activity 窗口内的叠层页面](issues/kotlin/2026-09-18-compose-modal-bottom-sheet-covers-in-window-overlay.md) | android | compose, material3, modal-bottom-sheet, window, z-order, overlay, ime |

## swift

| 状态 | 日期 | 标题 | 端 | 标签 |
|---|---|---|---|---|
| solved | 2026-10-09 | [SwiftUI 对 ignoresSafeArea 的 GeometryReader 容器整体 offset 做键盘避让，容器被拉高重新居中，上移量只生效一半](issues/swift/2026-10-09-swiftui-offset-safe-area-container-half-lift.md) | ios | swiftui, keyboard, keyboard-avoidance, offset, geometryreader, ignoressafearea, safe-area, scaleeffect |
| solved | 2026-10-09 | [SwiftUI 给全部按钮统一加行为（点击音）时，没写 buttonStyle 的默认样式按钮被漏掉](issues/swift/2026-10-09-swiftui-global-button-style-misses-default.md) | ios | swiftui, button, buttonstyle, primitivebuttonstyle, sound-effect, audit, code-review |
| workaround | 2026-10-09 | [iPad 模拟器浮动键盘开着时，XCUITest 点页面按钮第一下被吞掉、动作不触发](issues/swift/2026-10-09-simulator-floating-keyboard-swallows-tap.md) | ios | xcuitest, ios-simulator, ipad, keyboard, floating-keyboard, ui-testing, tap |
| solved | 2026-09-21 | [SwiftUI .id(x).onAppear：只换 id 时挂在 .id 外层的 onAppear 不再触发](issues/swift/2026-09-21-swiftui-onappear-outside-id-not-refired.md) | ios | swiftui, id, identity, onappear, task, side-effect, prefetch, cache-hit, autoplay |
| solved | 2026-09-20 | [SwiftUI 方向可变的横滑换页 transition：.transition 挂在 .id 外层，方向状态与 id 同一次更新即可正确翻转](issues/swift/2026-09-20-swiftui-directional-transition-outside-id.md) | ios | swiftui, transition, asymmetric, move-edge, id, identity, animation, paging, direction |
| solved | 2026-09-17 | [SwiftUI 网络图片优先用 Kingfisher：AsyncImage 无磁盘缓存、无失败占位与取消](issues/swift/2026-09-17-swiftui-asyncimage-no-disk-cache-prefer-kingfisher.md) | ios | swiftui, asyncimage, kingfisher, image-cache, network-image, spm, xcodegen, placeholder |
| solved | 2026-09-17 | [SwiftUI 分层绘制的按钮用 .plain 样式按下出现重影](issues/swift/2026-09-17-plain-button-style-ghosts-layered-label.md) | ios | swiftui, button, buttonstyle, plain, opacity, ghosting |
| solved | 2026-09-15 | [SwiftUI 动画中途用 .id 重建子视图会和父容器动画脱节（常驻底部弹窗快速重开时白底先到、内容慢半拍）](issues/swift/2026-09-15-swiftui-id-reidentify-during-animation-desync.md) | ios | swiftui, id, identity, animation, offset, bottom-sheet, state-reset |
| solved | 2026-09-14 | [SwiftUI ZStack 里 if + transition 的自绘弹层关闭时瞬间消失（移除时掉层被盖住），需要 zIndex](issues/swift/2026-09-14-swiftui-zstack-removal-transition-hidden.md) | ios | swiftui, zstack, transition, zindex, animation, bottom-sheet, overlay |
| solved | 2026-09-14 | [SwiftUI clipShape/clipped 不裁命中区：溢出裁剪框的装饰图在 ZStack 里吞掉遮罩和按钮的点击](issues/swift/2026-09-14-swiftui-clipshape-hit-testing-overflow.md) | ios | swiftui, clipshape, contentshape, hit-testing, zstack, offset, overlay, tap-gesture |
| solved | 2026-09-10 | [navigationDestination(isPresented:) 绑派生 Binding 导致 pop 后再 push 一页空白页](issues/swift/2026-09-10-navigation-destination-derived-binding-phantom-push.md) | ios | swiftui, navigationstack, navigationdestination, binding, state, pop, flash |
| solved | 2026-09-08 | [模拟器 Keychain 中的 mock token 跨构建残留导致 live 构建 401 登出](issues/swift/2026-09-08-simulator-keychain-token-persists.md) | ios | simulator, keychain, mock, auth, 401, simctl |
| solved | 2026-09-08 | [#Preview 引用 #if DEBUG 符号导致 Release 构建失败](issues/swift/2026-09-08-preview-debug-only-symbol-release-build.md) | ios | swiftui, preview, release-build, xcodebuild, debug-macro |
| solved | 2026-09-08 | [NavigationLink destination 视图的 init 随父视图每次 body 求值重复执行](issues/swift/2026-09-08-navigationlink-destination-eager-init.md) | ios | swiftui, navigationlink, performance, main-thread, state, disk-io |

## wechat-mp

| 状态 | 日期 | 标题 | 端 | 标签 |
|---|---|---|---|---|
| solved | 2026-10-05 | [自定义 tabBar 盖在页面弹层之上，z-index 再大也盖不住](issues/wechat-mp/2026-10-05-custom-tab-bar-above-page-overlay.md) | wechat | custom-tab-bar, tabbar, z-index, overlay, bottom-sheet |
| solved | 2026-10-03 | [rpx 向下取整成整数 px，按盒子拉伸的 SVG 背景图被等比缩小、两端图形往里挪](issues/wechat-mp/2026-10-03-rpx-floor-shrinks-stretched-svg-background.md) | wechat | rpx, wxss, svg, data-uri, background-size, preserveaspectratio, pixel-rounding, layout |
