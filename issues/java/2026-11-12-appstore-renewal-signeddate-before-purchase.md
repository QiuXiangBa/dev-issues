---
title: "Apple 真实续订 signedDate 可早于 purchaseDate，跨字段顺序校验会误拒可信交易"
stack: "java"
platform: ["backend"]
versions: ["Java 17", "App Store Server Library 5.2.0", "iOS 27.0.1 (Sandbox client)"]
tags: ["storekit", "app-store-server-api", "jws", "signed-date", "purchase-date", "timestamp-validation"]
project: "<sample-project>"
status: "solved"
date: "2026-11-12"
---

## 现象

真实 Sandbox 续订在 StoreKit 本地返回 `.verified`，服务端却在交易时间字段检查处拒绝。应用可能已显示新周期或本地有效交易，但服务端未保存该状态。

问题条件类似：

```java
if (signedDate < purchaseDate) {
    throw invalidTransaction();
}
```

这条附加的跨字段顺序约束会拒绝签名时间早于购买时间的真实交易。下文数值和业务类型均为合成示例；不记录真实 SKU、账号、交易标识或原始 JWS。

## 原因

Apple 的 `signedDate` 表示 App Store 签署 JWS 数据的 UNIX 毫秒时间；`purchaseDate` 描述相应购买、恢复或订阅相关收费事件的时间，同样使用 UNIX 毫秒。两项定义本身不承诺 `signedDate >= purchaseDate`。[signedDate](https://developer.apple.com/documentation/appstoreserverapi/signeddate)、[purchaseDate](https://developer.apple.com/documentation/appstoreserverapi/purchasedate)

本次真实 Sandbox 观察到已验签续订的签名时间早于其购买时间约 46 秒。这个观测足以否定上述无依据的拒绝条件，不代表所有环境总会提前签名，也不构成固定提前量的协议保证。

### 必须比较实际被拒对象的字段

不要在问题发生后 GET 同一交易，再把新响应中 JWS 的签名时间当作原始拒绝载荷的签名时间。重新签发的数据可能带来不同的 `signedDate`；本次分析应追踪实际接收对象的验证结果和解码元数据。

只保存脱敏后的比较结果、验证阶段及所用对象来源。外层通知和内层交易各自有字段，不能混用两层 `signedDate`。真实账号/交易标识、认证材料和原始 JWS 不进入知识库。

## 解决方案

移除未由契约支持的 `signedDate` 与 `purchaseDate` 大小关系，分别验证各字段。保留原有验签、应用/环境/商品、账号绑定及归属保护；只接收已通过对应验证边界的数据。

```java
VerifiedTransaction tx = verifier.verifyAndDecode(input);
requireApplicationEnvironmentProductAndAccount(tx, currentAccount);

Long purchaseDate = tx.purchaseDate();
Long signedDate = tx.signedDate();
long now = clock.millis();
long maxFutureSkew = 300_000L; // 示例容差，由项目策略决定
if (purchaseDate == null || purchaseDate < 0
        || signedDate == null || signedDate < 0
        || signedDate > now + maxFutureSkew) {
    throw invalidTransaction();
}
// 不再增加 signedDate >= purchaseDate 条件。
persistWithOwnershipAndOrdering(tx);
```

同环境原交易的唯一归属、分布式锁/数据库事务，以及购买周期和同周期签名时间的幂等/乱序规则继续生效。有效签名不等于当前权益有效；到期、撤销或已升级交易仍按服务端状态规则处理。

### 合成回归示例

```text
signedDate   = 1_000_000 ms
purchaseDate = 1_046_000 ms
expiresDate  = 1_346_000 ms
serverNow    = 1_050_000 ms
```

签名比购买早 46 秒，但两个时间非负，签名没有超过允许的未来上界。只要其他验证条件满足，不能仅凭这两个字段的先后关系拒绝。

使用固定 Clock，通过实际 HTTP/数据库边界检查：

- 旧实现会拒绝上述正例；修复后核对接受结果、落库字段及后续权益。
- 非空/非负边界及签名时间超出未来容差时，仍须拒绝且无落库/无权益。
- 时间顺序放宽后，错误应用/环境/商品/账号或归属冲突仍不能通过。
- 不把数据测试替身当作真实 Apple 签名测试。

### 验证范围

实际修复先在旧代码复现正例红灯，再通过 4 项定向 HTTP/H2 回归；完整 JDK17 构建 100 项测试全绿、无跳过，包含 3 项真实隔离 Redis 集成测试。定向测试在验签边界使用“已验证交易”替身，证明的是后续字段校验、持久化及拒绝边界，不证明 Apple 已签发这些合成数据。

部署后另有真实 Sandbox 证据：一笔同类早签续订已归属正确账号并持久化，采样时属于有效、未撤销周期。该证据证明这类真实交易能够入库，不代表原来每一笔失败载荷已重放，也不证明全部客户端 `verify → didSync → finish`、恢复或退款链已完成。

## 相关链接

- [Apple：signedDate](https://developer.apple.com/documentation/appstoreserverapi/signeddate)；[Markdown](https://developer.apple.com/documentation/appstoreserverapi/signeddate.md)。
- [Apple：purchaseDate](https://developer.apple.com/documentation/appstoreserverapi/purchasedate)；[Markdown](https://developer.apple.com/documentation/appstoreserverapi/purchasedate.md)。
