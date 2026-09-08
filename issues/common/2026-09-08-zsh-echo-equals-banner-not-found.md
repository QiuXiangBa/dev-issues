---
title: "zsh 中 echo ====X==== 分隔横幅触发 =cmd 展开并中断整条命令"
stack: common
platform: []
versions: [zsh 5.9, macos 26.6]
tags: [zsh, shell, claude-code, echo, equals-expansion]
project: xuejieai
status: solved
date: 2026-09-08
---

## 现象

在 zsh 里（包括 Claude Code 的 Bash 工具，它用登录 shell 执行命令）拼多段命令，用 `echo ====SECTION====` 做分隔：

```bash
echo ====BUILD==== && xcodebuild ... && echo ====TEST==== && swift test
```

报错并且**后面的命令一条都不执行**：

```
(eval):1: ===BUILD==== not found
```

同样的命令在 bash 下正常。

## 原因

zsh 默认开启 `EQUALS` 选项：以 `=` 开头的未引用单词会被当作 `=command` 形式做文件名展开，替换成 `command` 的可执行路径（等价于 `whence -p`）。`====BUILD====` 被解析为查找名为 `===BUILD====` 的命令，找不到就报 `not found`，而且这是解析阶段的错误，整行命令直接中止，不是 `echo` 单独失败。

bash 没有这个展开，所以从 bash 习惯带过来的横幅写法在 zsh 里会炸。

## 解决方案

分隔横幅加引号，或者不用 `=` 开头：

```bash
echo "-- BUILD --"
echo '=== BUILD ==='
```

如果脚本里大量用到以 `=` 开头的字面量，也可以关掉这个选项：

```bash
setopt noequals
```

判断当前 shell 是不是 zsh：`echo $ZSH_VERSION`，非空就是。

## 相关链接

- https://zsh.sourceforge.io/Doc/Release/Expansion.html#Filename-Expansion
- https://zsh.sourceforge.io/Doc/Release/Options.html#index-EQUALS
