---
title: "Spine 动画被显式打断后混出 entry 仍触发 Complete"
stack: "common"
platform: []
versions: ["spine-cpp 4.3", "macOS host regression", "HarmonyOS 7.0.0.107 / API 26"]
tags: [spine, spine-cpp, animation, mixing, callback, lifecycle, cancellation]
project: "native-rendering-example"
status: solved
date: "2026-11-17"
---

## 现象

应用要求“一次性动作被显式替换后，不再执行它的完成回调”。监听 AnimationState 的 Complete 后，早期打断看似正常，但在动作快结束时切到另一个动作，旧动作仍可能触发 Complete，造成业务继续执行已取消的后续步骤。

本次复现设置非零混合时长 `defaultMix = 0.25s`，通过 `addAnimation(..., delay=0)` 为单次动作排队循环 idle，再在单次动作结束前的混合区间内显式切换。连续重放还可能碰到 TrackEntry 池的地址复用。默认混合时长为 0，不能省略该配置后声称一定复现此提前混入边界。

本次用真实骨骼资源的宿主机回归先复现了“应为 0 次、实际收到旧 Complete”，修复后补充尾部打断、重放与自然排队回归通过。

## 原因

Spine 的 Complete 表示 TrackEntry 到达动画循环/结束时机，不是应用层的“未取消地完成”承诺。混出 entry 仍可推进时间并派发 Complete；Interrupt 也不等于立刻销毁或禁止后续 Complete。

当有前序 entry 且 `delay <= 0` 时，本版本 `addAnimation` 会将启动延迟计算为 `max(delay + last.getTrackComplete() - mixDuration, 0)`。本次配置非零 mixDuration（0.25s）、传入 delay=0，因此排队动作会在旧动作真正结束前开始混入：当前 track 可能已经是 idle，旧单次动作藏在 `mixingFrom` 链中。

这不是所有 `addAnimation` 调用的必然结果：默认 mix 为 0；较大的正 delay 也可能让下一动作更晚才开始。复现时需要核对实际生效的 mixDuration、排队 delay 与打断时刻。

因此两种简单过滤都不正确：

- 只取消 `state.getTrack(track)`：会漏掉旧 mixingFrom 动作。
- 一律丢弃 Interrupt、混出 entry 或“不是当前 entry”的 Complete：会误杀正常排队动作的合法完成。

这是 runtime 事件语义与应用取消语义的差别，不把它描述为 Spine 自身违反事件契约的 bug。

## 解决方案

仅在应用的**显式替换入口**记录取消，取消当前 track 及其整条旧 mixingFrom 链；自然排队不做取消。

以下为封装内部片段，`state`、`skeletonData`、`cancelledEntries` 与完成事件队列均归同一个实例所有，不是独立可编译的类定义：

```cpp
// 先验证请求；无效请求不能取消当前有效动画。
if (track < 0 || !skeletonData.findAnimation(name.c_str())) return false;
const size_t trackIndex = static_cast<size_t>(track);
for (spine::TrackEntry *entry = state.getTrack(trackIndex);
     entry != nullptr; entry = entry->getMixingFrom()) {
    cancelledEntries.insert(entry);
}
state.setAnimation(trackIndex, name.c_str(), loop);
```

`cancelledEntries` 使用 `std::unordered_set<spine::TrackEntry *>`。在 AnimationState 监听器中：

```cpp
if (entry == nullptr) return;
if (type == spine::EventType_Dispose) {
    cancelledEntries.erase(entry);
} else if (type == spine::EventType_Complete &&
           cancelledEntries.count(entry) == 0) {
    completed.push_back(entry->getAnimation().getName().buffer());
}
```

关键约束：

1. 不在普通 `addAnimation` 排队入口取消；自然排队仍应完成。
2. Dispose 时删除标记，防止池复用相同地址时把新 entry 当成已取消。
3. 不依赖直接析构派发 Dispose：本次 spine-cpp 4.3 的 `AnimationState::~AnimationState()` 直接删除 entry 和事件队列，不发送 Dispose；取消集合随其所属封装实例一起销毁。销毁前解绑 listener 可以作为额外防护，特别是销毁路径还会主动调用可能派发事件的 `clearTrack` / `clearTracks` 等操作时；不能把这种主动清理与直接析构混为一谈。
4. 收集事件后再向业务回调，避免事件遍历期间直接修改动画状态。
5. 这套策略适用于“显式替换会取消旧动作”的产品语义；若需要混出动作继续通知完成，应采用不同策略，而非照抄过滤。

### 回归与边界

- 先设置 `defaultMix=0.25s`；有 queued idle 的用例通过 `addAnimation(..., delay=0)` 排队。动作早期及结束前两个时刻显式打断，分别覆盖有/无 queued idle：旧完成计数都应为 0。
- 无效动画名、负 track 请求不影响原动作自然完成及排队 idle。
- 包含未 apply 就再次替换、尾部替换和自然结束的连续 12 轮重放：每轮只有替换后的新动作完成一次。
- 自然 `idle → 单次动作 → idle` 仍应恰好完成一次，不能为了消除旧回调而屏蔽所有混出事件。
- 本次上述宿主机回归通过，API 26 模拟器额外验证了自然完成、显式打断和组件重建；不宣称所有 Spine 版本、clearTrack 等其他取消入口已覆盖。
- platform 暂为空数组；原生事件逻辑与宿主 UI 无关，实际运行端见 versions。

## 相关链接

- [Spine AnimationStateListener 事件语义](https://esotericsoftware.com/spine-api-reference#AnimationStateListener)
- [Spine AnimationState.addAnimation](https://esotericsoftware.com/spine-api-reference#AnimationState-addAnimation)
- [Spine 官方 runtimes：spine-cpp 4.3](https://github.com/EsotericSoftware/spine-runtimes/tree/4.3/spine-cpp)
