---
title: "鸿蒙 AVPlayer 退后台即被系统暂停（StateChangeReason.BACKGROUND）：未接入 AVSession"
stack: "common"
platform: []
versions: ["DevEco Studio 26.0.0", "HarmonyOS 7.0.0.107 / API 26 模拟器", "HarmonyOS 5.0.1 / API 13 模拟器"]
tags: [harmonyos, arkts, avplayer, avsession, background-audio, continuous-task, background-running, audio-playback, state-change]
project: "<鸿蒙项目>"
status: solved
date: "2026-11-18"
---

## 现象

适用场景：HarmonyOS 应用用 `@kit.MediaKit` 的 AVPlayer 播音频（有声读物、逐句朗读等），希望退到后台后继续播放。

应用没有创建 AVSession 时，按 Home 退到后台后，播放很快停止：
- `stateChange` 回调收到 `'paused'`，`reason` 为 `media.StateChangeReason.BACKGROUND`（值 2），不是应用自己调用的 `pause()`（那种情况是 `USER` = 1）；
- API 13 模拟器上，约在按 Home 后 1.4s 被暂停；API 26 模拟器上，按 Home 后同样随即被暂停；
- 回到前台后**不会自动继续**。应用如果只按自己调用的 `pause()` 维护状态，界面会一直显示「播放中」，实际已经停了。

对照组（同一份代码，只改后台相关部分）：

| 组合 | 退后台后的表现（模拟器） |
|---|---|
| 没有 AVSession，也没有长时任务 | 随即被系统暂停，`reason = BACKGROUND` |
| 有 AVSession，没有长时任务 | 继续播放；后台暂停 90s 后也能继续 |
| 有 AVSession，也有 `AUDIO_PLAYBACK` 长时任务 | 继续播放，逐句串播到结束 |

「只有长时任务、没有 AVSession」的组合本次没有单独测试。

## 原因

SDK 声明（`@ohos.multimedia.media.d.ts`）对 `StateChangeReason.BACKGROUND` 的说明是：

> State transition caused by background system behavior. For example, if an application does not have the permission of Media Controller, the application is forcibly suspended or stopped by the system when it switches to the background.

也就是说，系统会对退到后台、但没有媒体会话的应用强制暂停或停止播放。系统日志可以印证这一点：后台新起一个音频流时，AudioRenderer 会先询问 AVSession 服务（下面的 uid / pid 已省略）：

```
C02b91/AVSession: [IsAudioPlaybackAllowed()-avsession_service.cpp] uid=… pid=… hasSession=1 isBack=1 isSystem=0
C02b83/AudioRenderer: [IsAllowedStartBackgroud]AVSession IsAudioPlaybackAllowed is: 1
```

因此，即使在后台按句子逐个新建 AVPlayer，只要会话存在，也允许起播。

另一个容易误判的地方：模拟器不会冻结后台应用，所以「有会话、没有长时任务」在模拟器上也能一直播放。长时任务的实际保活作用（防止被挂起或查杀）在模拟器上测不出来，需要真机验证。

## 解决方案

后台音频需要同时具备两样东西：AVSession 和 `AUDIO_PLAYBACK` 长时任务。两者都要在**前台**（用户点击播放时）建立好，不要等退到后台再补。

1. `module.json5`：

```json5
"requestPermissions": [{ "name": "ohos.permission.KEEP_BACKGROUND_RUNNING" }],
// 对应的 ability 中：
"backgroundModes": ["audioPlayback"],
```

2. 起播时建立会话并申请长时任务：

```typescript
const agent = await wantAgent.getWantAgent({
  wants: [{ bundleName: context.abilityInfo.bundleName, abilityName: context.abilityInfo.name }],
  actionType: wantAgent.OperationType.START_ABILITY,
  requestCode: 0,
  actionFlags: [wantAgent.WantAgentFlags.UPDATE_PRESENT_FLAG],
});
const session = await avSession.createAVSession(context, 'Tag', 'audio');
session.on('play', () => player.play());
session.on('pause', () => player.pause());
// playNext / playPrevious / stop 按需注册
await session.setLaunchAbility(agent);
await session.activate();
await session.setAVMetadata({ assetId: id, title, artist, mediaImage: coverUrl });
await session.setAVPlaybackState({ state: avSession.PlaybackState.PLAYBACK_STATE_PLAY }); // 不要传 speed: 0，见相关记录
await backgroundTaskManager.startBackgroundRunning(
  context, backgroundTaskManager.BackgroundMode.AUDIO_PLAYBACK, agent);
```

3. AVPlayer 设置媒体类用途，例如在 `'initialized'` 状态里设 `audioRendererInfo = { usage: audio.StreamUsage.STREAM_USAGE_AUDIOBOOK, rendererFlags: 0 }`，再调用 `prepare()`。
4. 兜底处理系统强制暂停：`stateChange` 收到 `'paused'` 且 `reason === media.StateChangeReason.BACKGROUND` 时，把应用自己的播放状态和播控中心状态同步为「已暂停」，续播走正常的 `play()`。
5. 停止、播完或离开页面时，依次调用 `stopBackgroundRunning(context)`、`session.deactivate()`、`session.destroy()`。

核查命令（只读）：`hidumper -s AVSessionService -a '-show_session_info'` 查看会话是否激活、是否置顶；`-a '-show_metadata'` 查看标题、封面。`hidumper -s BackgroundTaskManager -a '-C --all'` 在上述模拟器上没有输出，长时任务状态只能靠应用日志确认。

## 相关链接

- [Media Kit AVPlayer（StateChangeReason）](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/arkts-apis-media)
- [AVSession API 参考](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/js-apis-avsession)
- [长时任务（backgroundTaskManager）](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/js-apis-resourceschedule-backgroundtaskmanager)
- 相关记录：`2026-11-18-avsession-playback-state-speed-zero-401.md`（setAVPlaybackState 的 speed 不能传 0）
