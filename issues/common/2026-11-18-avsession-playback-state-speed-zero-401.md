---
title: "鸿蒙 AVSession setAVPlaybackState 传 speed: 0 报 401 invalid parameters，播控中心暂停图标不切换"
stack: "common"
platform: []
versions: ["DevEco Studio 26.0.0", "HarmonyOS 7.0.0.107 / API 26 模拟器", "HarmonyOS 5.0.1 / API 13 模拟器"]
tags: [harmonyos, arkts, avsession, avplaybackstate, playback-state, media-controls, control-center, background-audio]
project: "<鸿蒙项目>"
status: solved
date: "2026-11-18"
---

## 现象

适用场景：HarmonyOS 应用通过 `@kit.AVSessionKit` 的 AVSession 接管系统播控中心 / 锁屏控制，并按 Android `MediaSession` 的习惯，暂停时上报 0 倍速：

```typescript
await session.setAVPlaybackState({
  state: avSession.PlaybackState.PLAYBACK_STATE_PAUSE,
  speed: 0,
});
```

调用被拒，Promise 以 401 失败：

```
401 SetAVPlaybackState failed : native invalid parameters
```

可见表现：
- 在播控中心点暂停，播放器确实暂停了，但图标仍然停在「暂停」键，不会切回「播放」；
- 再点一次，系统发来的还是 `pause` 指令（不是 `play`），用户无法从播控中心继续播放；
- 如果调用处没有 catch 并打日志，就只剩「图标不对」这一个现象，很难定位。

## 原因

AVSession native 层会校验 `AVPlaybackState.speed`，0 被当作非法参数，整个 `setAVPlaybackState` 调用失败，`state` 也就没有更新。

SDK 声明（`@ohos.multimedia.avsession.d.ts`）中 `speed?: number` 只写了「Current playback speed」，没有标注取值范围。这个错误来自照搬 Android 的写法：Android 的 `PlaybackStateCompat` 暂停时惯例上报 0 倍速。

## 解决方案

只上报 `state`，不传 `speed`：

```typescript
const playbackState: avSession.AVPlaybackState = {
  state: playing ? avSession.PlaybackState.PLAYBACK_STATE_PLAY
                 : avSession.PlaybackState.PLAYBACK_STATE_PAUSE,
};
await session.setAVPlaybackState(playbackState);
```

- 修改后，播控中心和锁屏上的播放 / 暂停图标都能正确切换，点击后交替收到 `play` / `pause` 指令。已在 API 26 和 API 13 模拟器上验证。
- `setAVPlaybackState` / `setAVMetadata` 一定要 catch 并记录 `code` / `message`，否则参数错误不会有任何提示。
- 确实需要上报倍速时，应传真实的非零倍速。本次没有验证暂停状态下传非零倍速的表现。

## 相关链接

- [AVSession API 参考（AVPlaybackState）](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/js-apis-avsession)
- 相关记录：未接入 AVSession 时退后台被系统暂停（`2026-11-18-avplayer-background-pause-without-avsession.md`）
