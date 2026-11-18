---
title: "macOS 同开 Tailscale DNS 与代理隧道时默认 DNS 超时，模拟器和命令行工具解析失败"
stack: "common"
platform: []
versions: ["macOS 26.6.2", "Tailscale 1.104.6", "Shadowrocket 2.2.92", "HarmonyOS 模拟器 5.0.1 (API 13)", "DevEco Studio 26.0.0"]
tags: [dns, tailscale, magicdns, shadowrocket, vpn, tun, emulator, slirp, harmonyos, gh, cli, macos]
project: "<鸿蒙项目>"
status: solved
date: "2026-11-18"
---

## 现象

macOS 开发机同时运行 Tailscale（开着「Use Tailscale DNS」）和 Shadowrocket（隧道模式）。浏览器访问正常，但以下几处同时出问题：

- `gh` 报 `error connecting to api.github.com`，`curl` 显示卡在域名解析。
- 鸿蒙模拟器里的应用连不上任何域名（本次是 WebSocket 握手超时）。模拟器 shell 里 `ping <域名>` 报 `ping: <域名>: Try again`，但 `ping <公网 IP>` 正常，说明网络本身是通的，只有解析失败。
- 主机上 `dscacheutil -q host -a name <域名>` 没有结果，`dig +time=2 +tries=1 +short <域名>` 报 `connection timed out; no servers could be reached`。

## 原因

`scutil --dns` 显示系统默认解析器的第一个 nameserver 是 Tailscale MagicDNS 的 `100.100.100.100`（`route -n get 100.100.100.100` 走 Tailscale 的 utun 接口）。和代理隧道同时开时，发往它的查询全部超时。

分别指定 DNS 服务器测试：

| DNS | 结果 |
|---|---|
| 默认解析器（`100.100.100.100`） | 超时 |
| `8.8.8.8` | 超时 |
| `114.114.114.114` | 正常 |
| Shadowrocket 的 `198.18.0.2`（fake-IP） | 正常 |

两个隧道具体怎么冲突没有深究，只确认了关掉 Tailscale DNS 就恢复。

影响范围：

- **命令行工具**：`gh`、`curl`、`git` 不读 macOS 系统代理，走直连解析，所以失败。浏览器走系统 HTTP 代理，由代理在远端解析域名，所以不受影响。
- **模拟器**：模拟器网络经宿主机用户态 NAT（QEMU slirp 一类），客户机的 DNS 请求转给宿主机默认解析器，于是跟着失败。鸿蒙模拟器 `/etc/resolv.conf` 里写的是 `114.114.114.114` / `8.8.8.8`，但改不了结果，看来系统网络服务用的不是这个文件（由现象推断，未查证）。Android 模拟器同属这一类 NAT，可能有同样表现（本次未实测）。

## 解决方案

1. **先确认是 DNS 问题**：

```bash
scutil --dns | grep -E 'resolver #|nameserver\[' | head
dig +time=2 +tries=1 +short <域名>                     # 默认解析器
dig +time=2 +tries=1 +short @100.100.100.100 <域名>    # Tailscale DNS
dig +time=2 +tries=1 +short @114.114.114.114 <域名>    # 公共 DNS 对照
```

   默认解析器和 `@100.100.100.100` 都超时、公共 DNS 正常，就是这个问题。

2. **根治**：在 Tailscale 设置里关掉「Use Tailscale DNS」。命令行等价写法是 `tailscale set --accept-dns=false`（本次未实测）。关掉后默认 DNS 落到代理隧道的 `198.18.0.2`，`dig` 立即能返回地址。**已在运行的模拟器不用重启就恢复了解析**，应用重试即可。
   代价是失去 MagicDNS，tailnet 内的机器名不能再直接解析，需要时改用 Tailscale IP。

3. **只想临时让命令行工具可用**：给命令带上系统代理，端口用 `scutil --proxy` 查：

```bash
export HTTPS_PROXY=http://127.0.0.1:<代理端口> HTTP_PROXY=http://127.0.0.1:<代理端口>
```

   这一步对模拟器无效，模拟器里的应用不读宿主机环境变量。

## 相关链接

- 同为 Tailscale DNS 引起、但机制不同的服务器场景（Linux CGNAT 防火墙规则丢弃 DNS 回包）：`issues/common/2026-11-11-tailscale-systemd-service-dns.md`
