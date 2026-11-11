---
title: "Tailscale 阻断云内 DNS 回包：用 systemd 为单个服务隔离解析配置"
stack: "common"
platform: [backend]
versions: ["Alibaba Cloud Linux 3"]
tags: [tailscale, systemd, dns, cgnat, resolv-conf, mount-namespace, unknown-host, rds]
project: "littleluck"
status: workaround
date: "2026-11-11"
---

## 现象

Linux 云主机上已有 Tailscale 和其他常驻服务。新增的 systemd Java 服务启动后，连接 VPC 内 RDS 时出现 `java.net.UnknownHostException: <DB_HOSTNAME>`，数据库连接池无法建立连接。

宿主机的 `/etc/resolv.conf` 优先使用 Tailscale 的 `100.100.100.100`，并包含 IPv6 解析器；目标数据库域名经这条解析链无法正常返回结果。单独查询云厂商 VPC DNS 也失败，但分别查询 `223.5.5.5`、`223.6.6.6` 均能返回目标数据库的私网地址，且从该主机到返回地址的 TCP 3306 可达。

复现环境为 Alibaba Cloud Linux 3、systemd、Tailscale；systemd、Tailscale 和 JVM 的精确版本没有留存，不能据此认定所有版本行为相同。此问题发生在系统解析与防火墙层，其他语言的进程也可能受到影响。

## 原因

需要区分宿主机默认解析链和 VPC DNS 回包被过滤这两件事。更换查询的 DNS 地址后，仍可能在回包路径失败。

本次检查发现，Tailscale 的 `ts-input` 链含以下规则：

```text
-A ts-input -s 100.64.0.0/10 ! -i tailscale0 -j DROP
```

该规则阻断来自 CGNAT 地址段、却不经过 Tailscale 接口进入的流量。云厂商 VPC DNS 恰好位于这个地址段，所以正常网络接口收到的 DNS 回包也被丢弃。路由存在并不能证明 DNS 查询可以完成；只把 `/etc/resolv.conf` 改回 VPC DNS 也不能绕过这条过滤规则。这个机制与 Tailscale 官方描述的 [Linux CGNAT 互操作限制](https://tailscale.com/docs/reference/cgnat-interoperability) 一致。

本次没有改变共享宿主机的 DNS、Tailscale 或防火墙，而是为新增服务选择已实测可用的解析器，并通过 systemd 的挂载命名空间隔离配置。这是单个服务的绕行方案，没有消除宿主机上的 CGNAT 冲突。

## 解决方案

### 1. 先确认候选解析器和目标网络都可用

查询私有域名可能把查询名称交给公共 DNS；先确认这一边界符合环境要求，再执行测试。以下名称与路径全部为占位示例，使用时替换成自己的值：

```bash
db_name=db.example.com
dig +time=2 +tries=1 @223.5.5.5 "$db_name" A
dig +time=2 +tries=1 @223.6.6.6 "$db_name" A
nc -vz -w 3 <RESOLVED_PRIVATE_IP> 3306
```

逐个检查候选 DNS 是否回答目标域名、回答是否为预期私网地址、该地址的路由和数据库端口是否可达。域名可能存在 CNAME，不能只看有无返回行。**本次两个公共解析器均回答了被测 RDS 的私网地址，不代表公共 DNS 能解析所有 RDS 或任意私有 DNS 区域。** 如果候选解析器不知晓目标名称，或不允许把私有名称发给公共 DNS，应先提供可达且获准使用的私有解析器，再考虑服务内绑定。

排查回包过滤时只读检查即可：

```bash
sudo iptables -S ts-input
ip route get <VPC_DNS_IP>
```

### 2. 为目标服务准备专用 resolv.conf

例如创建 `/etc/example-app/resolv.conf`，由 root 管理，允许服务读取，内容为：

```conf
nameserver 223.5.5.5
nameserver 223.6.6.6
options timeout:2 attempts:2
```

然后在目标 unit 的 `[Service]` 段，或专属 drop-in `/etc/systemd/system/example-app.service.d/20-resolver.conf` 中加入：

```ini
[Service]
BindReadOnlyPaths=/etc/example-app/resolv.conf:/etc/resolv.conf
```

`BindReadOnlyPaths` 为 unit 建立只读绑定，作用于该 unit 的文件系统视图，宿主机的解析文件不会因此被替换。目标挂载路径、源文件及命名空间支持条件见 [systemd.exec 的 BindPaths / BindReadOnlyPaths 文档](https://www.freedesktop.org/software/systemd/man/253/systemd.exec.html#BindPaths=)。先用当前主机的 systemd 校验 unit，再加载并重启目标服务，让新进程使用新的视图及解析缓存：

```bash
sudo systemd-analyze verify example-app.service
sudo systemctl daemon-reload
sudo systemctl restart example-app.service
```

此专用文件没有继承宿主机的搜索域或 MagicDNS 配置，服务需要使用完整域名，并验证所有外部依赖的解析。

### 3. 在实际服务进程内验证

不能仅凭 unit 配置存在或宿主机上 `dig @候选DNS` 成功，就认定应用已经使用专用解析器：

```bash
service_pid=$(systemctl show --property=MainPID --value example-app.service)
test "$service_pid" -gt 0
sudo nsenter --target "$service_pid" --mount -- cat /etc/resolv.conf
sudo nsenter --target "$service_pid" --mount -- getent ahostsv4 "$db_name"
```

确认前一个命令读到专用文件、后一个命令返回预期私网地址，并核对实际挂载命名空间。还要检查 `/etc/nsswitch.conf` 的 `hosts:` 解析顺序：如果经 `nss-resolve` 转交宿主机 `systemd-resolved`，或应用自行使用 DoH/其他 DNS 客户端，仅绑定 `resolv.conf` 可能无效。`nss-resolve` 通过本机 Unix socket 与解析服务通信，见 [官方 nss-resolve 文档](https://www.freedesktop.org/software/systemd/man/253/nss-resolve.html)。最终仍需在真实应用中验证数据库连接和读写。

改动前后另行记录宿主机 `/etc/resolv.conf` 的 SHA-256，确认哈希一致；同时确认原有业务及 Tailscale 仍可用。文件哈希只证明文件内容未改变，不能代替业务检查。

### 本次验证结果与适用边界

- 实际 Java 服务命名空间中的解析文件与专用文件一致，目标数据库解析为预期私网地址。
- 数据库相关 HTTP 读写流程通过，测试创建的账号已经清理。
- 宿主机 `/etc/resolv.conf` 改动前后 SHA-256 一致；修改范围仅为新增服务，未修改共享 DNS、Tailscale、防火墙或其他服务配置。
- 以上结果适用于被测主机的挂载、NSS 与应用配置；更换发行版、解析链、网络或依赖域名后，需要重新验证。若要回退，删除该服务新增的绑定配置，重新加载 systemd 并重启该服务即可，专用文件可在确认不再引用后移除。

## 相关链接

- [Tailscale：CGNAT interoperability](https://tailscale.com/docs/reference/cgnat-interoperability) —— Linux CGNAT 过滤规则的机制说明；本文采用单服务 DNS 隔离，未套用该页的全局规则修改方案。
- [systemd.exec：BindPaths / BindReadOnlyPaths](https://www.freedesktop.org/software/systemd/man/253/systemd.exec.html#BindPaths=) —— unit 专属绑定挂载的语义；链接的文档版本不表示本次主机安装了该版本。
- [nss-resolve](https://www.freedesktop.org/software/systemd/man/253/nss-resolve.html) —— NSS 转交 systemd-resolved 的解析路径。
