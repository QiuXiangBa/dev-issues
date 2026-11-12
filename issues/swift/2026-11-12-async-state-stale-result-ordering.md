---
title: "同账号异步旧响应覆盖新权益与配额，需要发布 revision 与账号代际双重检查"
stack: "swift"
platform: ["ios"]
versions: ["iOS 27.0.1", "Xcode 27.1"]
tags: ["async", "revision", "race-condition", "entitlement", "quota", "account-scope"]
project: "<sample-project>"
status: "solved"
date: "2026-11-12"
---

## 现象

服务端已经接受新权益，客户端也曾收到可信状态，但稍早发出的概览或状态请求稍后返回，把界面和配额重新写回旧值。重新刷新后又恢复，看起来像权益交付偶发失败。

另一种表现是：权益标志更新了，个人资料中的同一状态或额度还停留在旧值；若后续概览刷新失败，矛盾状态会一直保留。所有示例均为通用状态模型与合成数据，不包含真实账号或产品。

## 原因

`@MainActor` 只串行执行同步片段。网络 `await` 之间允许其他任务进入，**开始顺序与完成顺序可以不同**。只检查账号 scope 能拒绝旧账号结果，却无法拒绝同一账号中已经过期的读取。

典型交错：

1. 概览读取 R1 已取得旧 profile 快照，另一并行子请求仍被阻塞。
2. 可信操作返回新状态 S2，客户端发布 S2 并开始刷新 R3。
3. R3 失败，S2 是最近已知状态。
4. R1 结束；账号没变，于是旧 profile、权益和额度整体覆盖 S2。

只对某一个权益字段增加保护也不够：发布旧 profile 仍可能把资料内的权益或额度带回来。将所有状态强制保 active 同样错误，会阻止新的到期或撤销状态生效。

## 解决方案

为同一组权益数据建立单调递增的**发布 revision**，与账号代际分别检查：

- 每个会发布权益的异步读取，在首次 `await` 前取得新 revision。
- 返回后先检查账号 scope；旧账号结果继续按原会话隔离规则拒绝。
- 同账号但 revision 过期时静默丢弃，不能伪装成账号失效。
- 概览中的 profile、权益、额度作为一致快照发布；过期概览整体丢弃。
- 可信状态通过集中入口，在第一次悬挂前递增 revision、发布状态与对应额度，再尽力刷新概览。刷新失败不能重新接纳更旧的快照。

以下为示意，DTO、API 和异常类型由项目提供：

```swift
@MainActor
func refreshOverview() async throws {
    let scope = accountScope
    entitlementRevision += 1
    let revision = entitlementRevision
    async let overview = api.overview()
    async let profile = api.profile()
    let snapshot = try await (overview, profile)
    guard scope == accountScope else { throw StateError.sessionChanged }
    guard revision == entitlementRevision else { return }
    publishOverview(snapshot) // 同步发布整份 profile、权益与额度
}

@MainActor
func acceptVerified(_ status: Status, scope: UUID) async {
    guard scope == accountScope, !isChangingAccount else { return }
    entitlementRevision += 1
    publishStatus(status)
    try? await refreshOverview()
}
```

`publishStatus` 应在同一 MainActor 同步片段更新独立权益、profile 内的权益、profile 额度及剩余额度。可使用当前已知的 used 和新状态携带的 limit；无限额度使用契约规定的可空 limit，不依据 active 标志偏爱某种结果。若 DTO 还含 unlimited 标记，也要同步更新。新的 expired/revoked 响应仍能恢复有限额度。

### 独立目录不能被权益 revision 饿死

若状态读取同时获取产品目录，较新的概览可能使旧状态结果失效。但目录本身仍需完成首次加载，否则页面随后用空列表加载商品。

```swift
let result = try await (catalogRequest, statusRequest)
guard scope == accountScope else { throw StateError.sessionChanged }
catalog = result.0                // 账号检查后独立发布目录
guard revision == entitlementRevision else { return }
publishStatus(result.1)
try await refreshOverview()
```

过期的状态不发布，也不能继续启动另一次概览来掩盖其旧写入。该 revision 是客户端发布次序，不是服务端交易历史版本；跨设备、数据库或交易乱序仍需要服务端的归属、周期和版本规则。

### 确定性回归

使用 actor gate/continuation 控制响应顺序，不依赖延时猜测：

| 场景 | 必须保持的结果 |
| --- | --- |
| 旧 profile 已准备、overview 另一请求阻塞；可信 active 到达且新刷新失败，再放旧读 | 不回滚权益、used、limit、剩余额度或整份 profile |
| 旧 free status 阻塞；可信 active 到达，再放旧 status | 静默丢弃，不启动掩盖结果的额外 overview |
| 旧 status 等待期间，新 overview 先发布 | 目录仍加载，权益及额度保留新值 |
| 更新后的 expired overview | 可以从 active 降为有限额度 |
| 更新后的 revoked status，随后 overview 失败 | 即时同步 profile 和额度，不保留无限额度 |
| 换账号后收到旧作用域可信回调 | 新账号状态不被修改 |

实际回归中，旧生产逻辑在前述旧读与额度场景出现预期红灯；最初的 revision 版本另在目录场景出现红灯。最终完整单元测试 70 项全部通过、无跳过，含这 6 项新增场景；Release 与两档提示 UI 也通过。

这些是受控 HTTP/状态测试；提示 UI 使用 Debug 结果夹具。它们不证明真实第三方交易已经完成验签、入库或 finish。数据库中存在权益也不能单独证明客户端整条交付链完成。

## 相关链接

- [Apple：onChange(of:perform:)](https://developer.apple.com/documentation/swiftui/view/onchange(of:perform:).md)：观察回调不是多个异步任务之间的业务原子事务。
- [相关：首次就绪与提示失效规则](2026-11-11-swiftui-bootstrap-notice-account-scope-race.md)：账号代际与首次初始化需要分别建模。
