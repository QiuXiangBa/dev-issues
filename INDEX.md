# 索引

由 `scripts/index.sh` 自动生成，不要手改。共 12 条。

## ai-tools

| 状态 | 日期 | 标题 | 端 | 标签 |
|---|---|---|---|---|
| solved | 2026-09-16 | [Figma 旋转存储的画板：多层 SVG 素材用 JSX 转 HTML 整页反旋转后 WKWebView 光栅化](issues/ai-tools/2026-09-16-figma-rotated-artboard-svg-assets-via-html.md) | ios, web | figma, mcp, design-to-code, svg-rasterize, wkwebview, tailwind, rotated-artboard, claude-code |
| solved | 2026-09-16 | [Figma 云端 MCP 未授权时改走桌面端 Dev Mode 本地 MCP 读设计稿](issues/ai-tools/2026-09-16-figma-mcp-unauthorized-use-desktop-dev-mode.md) | ios, web | figma, mcp, oauth, design-to-code, claude-code, json-rpc, svg-rasterize |
| solved | 2026-09-08 | [流式调用下 tool&#95;use 的 input 解析失败](issues/ai-tools/2026-09-08-tool-use-json-truncated.md) | backend | claude-api, tool-use, streaming, json-parse, max-tokens |

## common

| 状态 | 日期 | 标题 | 端 | 标签 |
|---|---|---|---|---|
| solved | 2026-09-08 | [zsh 中 echo ====X==== 分隔横幅触发 =cmd 展开并中断整条命令](issues/common/2026-09-08-zsh-echo-equals-banner-not-found.md) |  | zsh, shell, claude-code, echo, equals-expansion |

## swift

| 状态 | 日期 | 标题 | 端 | 标签 |
|---|---|---|---|---|
| solved | 2026-09-17 | [SwiftUI 网络图片优先用 Kingfisher：AsyncImage 无磁盘缓存、无失败占位与取消](issues/swift/2026-09-17-swiftui-asyncimage-no-disk-cache-prefer-kingfisher.md) | ios | swiftui, asyncimage, kingfisher, image-cache, network-image, spm, xcodegen, placeholder |
| solved | 2026-09-15 | [SwiftUI 动画中途用 .id 重建子视图会和父容器动画脱节（常驻底部弹窗快速重开时白底先到、内容慢半拍）](issues/swift/2026-09-15-swiftui-id-reidentify-during-animation-desync.md) | ios | swiftui, id, identity, animation, offset, bottom-sheet, state-reset |
| solved | 2026-09-14 | [SwiftUI ZStack 里 if + transition 的自绘弹层关闭时瞬间消失（移除时掉层被盖住），需要 zIndex](issues/swift/2026-09-14-swiftui-zstack-removal-transition-hidden.md) | ios | swiftui, zstack, transition, zindex, animation, bottom-sheet, overlay |
| solved | 2026-09-14 | [SwiftUI clipShape/clipped 不裁命中区：溢出裁剪框的装饰图在 ZStack 里吞掉遮罩和按钮的点击](issues/swift/2026-09-14-swiftui-clipshape-hit-testing-overflow.md) | ios | swiftui, clipshape, contentshape, hit-testing, zstack, offset, overlay, tap-gesture |
| solved | 2026-09-10 | [navigationDestination(isPresented:) 绑派生 Binding 导致 pop 后再 push 一页空白页](issues/swift/2026-09-10-navigation-destination-derived-binding-phantom-push.md) | ios | swiftui, navigationstack, navigationdestination, binding, state, pop, flash |
| solved | 2026-09-08 | [模拟器 Keychain 中的 mock token 跨构建残留导致 live 构建 401 登出](issues/swift/2026-09-08-simulator-keychain-token-persists.md) | ios | simulator, keychain, mock, auth, 401, simctl |
| solved | 2026-09-08 | [#Preview 引用 #if DEBUG 符号导致 Release 构建失败](issues/swift/2026-09-08-preview-debug-only-symbol-release-build.md) | ios | swiftui, preview, release-build, xcodebuild, debug-macro |
| solved | 2026-09-08 | [NavigationLink destination 视图的 init 随父视图每次 body 求值重复执行](issues/swift/2026-09-08-navigationlink-destination-eager-init.md) | ios | swiftui, navigationlink, performance, main-thread, state, disk-io |
