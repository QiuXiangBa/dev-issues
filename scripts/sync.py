#!/usr/bin/env python3
"""Synchronize explicitly selected records; never stage unrelated files."""
import argparse
import ipaddress
import re
import subprocess
import sys

from issues import ROOT, IssueError, generate_index, issue_path, parse, records


def git(*args, check=True, env=None):
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, encoding="utf-8",
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if check and result.returncode:
        raise IssueError("git {} 失败：\n{}".format(args[0], result.stderr.strip()))
    return result


def names(*args):
    return set(filter(None, git(*args, "-z").stdout.split("\0")))


def sensitive_findings(text):
    """Best-effort publication guard; never print the matching secret itself."""
    patterns = [
        ("私钥", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        ("访问密钥", r"\b(?:sk-(?:ant-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b"),
        ("凭据赋值", r'''(?i)\b(?:api[_-]?key|access[_-]?token|password|secret|authorization|cookie)\b["']?\s*[:=]\s*["']?([^\s"'`,;]+)'''),
        ("手机号", r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    ]
    placeholders = {"...", "xxx", "changeme", "none", "null", "bearer", "basic"}
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        for label, pattern in patterns:
            for match in re.finditer(pattern, line):
                if label == "凭据赋值":
                    value = match[1]
                    if (value.lower() in placeholders or any(c in value for c in "*<>${}")
                            or value.startswith(("os.environ", "os.getenv", "process.env"))):
                        continue
                findings.append((number, label))
        # Headers often have a scheme before their actual credential.
        if re.search(r"(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9._+/=-]{12,}", line):
            findings.append((number, "认证凭据"))
        for match in re.finditer(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line):
            try:
                address = ipaddress.ip_address(match[0])
            except ValueError:
                continue
            if any(address in network for network in PRIVATE_NETWORKS):
                findings.append((number, "内网 IP"))
        for match in re.finditer(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", line):
            domain = match[1].lower()
            if domain not in {"example.com", "example.org", "example.net"} and not domain.endswith(".example.com"):
                findings.append((number, "邮箱"))
        if re.search(r"\b[a-zA-Z0-9][a-zA-Z0-9.-]*\.(?:internal|corp|local)\b", line):
            findings.append((number, "内部域名"))
    return sorted(set(findings))


PRIVATE_NETWORKS = tuple(ipaddress.ip_network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def check_publication(path, text):
    parse(text, ROOT.joinpath(path).relative_to(ROOT))
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    for heading in ("现象", "原因", "解决方案"):
        match = re.search(r"^## " + heading + r"\s*\n(.*?)(?=^## |\Z)", body, re.M | re.S)
        if not match or not match[1].strip():
            raise IssueError(path + ": 请填写「" + heading + "」，不能发布空模板")
    findings = sensitive_findings(text)
    if findings:
        raise IssueError("发现疑似敏感信息，请脱敏后重试：\n" + "\n".join(
            "{}:{} {}".format(path, line, kind) for line, kind in findings))


def check_outgoing(upstream, selected):
    commits = git("rev-list", "--reverse", upstream + "..HEAD").stdout.splitlines()
    for commit in commits:
        parents = git("rev-list", "--parents", "-n", "1", commit).stdout.split()
        if len(parents) != 2:
            raise IssueError("待推送历史含合并提交，请先单独整理并审核历史")
        changed = names("diff", "--name-only", "--no-renames", commit + "^", commit)
        extra = changed - selected - {"INDEX.md"}
        if extra:
            raise IssueError("待推送提交含未指定文件：" + ", ".join(sorted(extra)))
        for path in changed:
            blob = git("show", commit + ":" + path, check=False)
            if blob.returncode:  # Deletion.
                continue
            if path == "INDEX.md":
                findings = sensitive_findings(blob.stdout)
                if findings:
                    raise IssueError("待推送历史 INDEX.md 含疑似敏感信息，请先清理该本地提交")
            else:
                check_publication(path, blob.stdout)


def rebase(upstream):
    result = git("rebase", upstream, check=False)
    while result.returncode:
        conflicts = names("diff", "--name-only", "--diff-filter=U")
        if conflicts == {"INDEX.md"}:
            generate_index(paths=tracked_records())
            git("add", "--", "INDEX.md")
            result = git("-c", "core.editor=true", "rebase", "--continue", check=False)
            continue
        if conflicts:
            raise IssueError("记录合并冲突：" + ", ".join(sorted(conflicts)) +
                             "\n解决后 git add <记录路径> && git rebase --continue，再执行原同步命令。"
                             "\n取消本次 rebase：git rebase --abort（保留 rebase 前的本地提交）。")
        raise IssueError("rebase 失败，请查看 Git 状态后重试：\n" + result.stderr.strip())


def tracked_records():
    return [path for path in names("ls-files") if path.startswith("issues/") and path.endswith(".md")]


def sync(args):
    selected = {issue_path(value).relative_to(ROOT).as_posix() for value in args.paths}
    if git("rev-parse", "--show-toplevel").stdout.strip() != str(ROOT):
        raise IssueError("必须在知识库自己的 Git 仓库中运行")
    for state in ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "sequencer"):
        state_path = git("rev-parse", "--git-path", state).stdout.strip()
        if (ROOT / state_path).exists():
            raise IssueError("已有未完成的 Git 操作，请先完成或取消：" + state)
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if branch.returncode:
        raise IssueError("当前是 detached HEAD，请切换到有 upstream 的分支")
    branch = branch.stdout.strip()
    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", check=False)
    if upstream.returncode:
        raise IssueError("当前分支没有 upstream，请先配置 git branch --set-upstream-to=<远端>/<分支>")
    upstream = upstream.stdout.strip()
    remote = git("config", "--get", "branch." + branch + ".remote").stdout.strip()
    destination = git("config", "--get", "branch." + branch + ".merge").stdout.strip()
    if remote == "." or not destination.startswith("refs/heads/"):
        raise IssueError("同步需要远端分支 upstream")
    allowed = selected | {"INDEX.md"}
    tracked = names("diff", "HEAD", "--name-only", "--no-renames")
    staged = names("diff", "--cached", "--name-only", "--no-renames")
    extra = (tracked | staged) - allowed
    if extra:
        raise IssueError("存在本次记录以外的已跟踪改动，请先单独提交或暂存到 stash：" + ", ".join(sorted(extra)))
    for path in selected:
        file = ROOT / path
        if file.exists():
            check_publication(path, file.read_text(encoding="utf-8"))
        elif git("cat-file", "-e", "HEAD:" + path, check=False).returncode:
            raise IssueError("记录不存在且不是已跟踪的删除：" + path)
    records([path for path in set(tracked_records()) | selected if (ROOT / path).exists()])
    # Fetch errors are not merge conflicts and leave the working tree untouched.
    git("fetch", "--quiet", "--", remote)
    check_outgoing(upstream, selected)
    if args.check:
        print("同步预检通过；将处理：" + ", ".join(sorted(selected)) + " 及 INDEX.md")
        return
    # INDEX.md is disposable generated output. Never carry its local diff into rebase.
    git("restore", "--source=HEAD", "--staged", "--worktree", "--", "INDEX.md")
    git("add", "--", *sorted(selected))
    staged = names("diff", "--cached", "--name-only")
    for path in staged:
        blob = git("show", ":" + path, check=False)
        if blob.returncode == 0:
            check_publication(path, blob.stdout)
    if staged:
        git("commit", "--quiet", "-m", args.message)
    rebase(upstream)
    generate_index(paths=tracked_records())
    git("add", "--", "INDEX.md")
    if names("diff", "--cached", "--name-only"):
        git("commit", "--quiet", "-m", "chore: regenerate issue index")
    check_outgoing(upstream, selected)
    git("push", "--quiet", "--", remote, "HEAD:" + destination)
    print("已同步：" + ", ".join(sorted(selected)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-m", "--message", default="update issues")
    parser.add_argument("--check", action="store_true", help="校验并 fetch，不修改工作区、不提交、不推送")
    parser.add_argument("paths", nargs="+", help="本次记录的仓库相对路径或绝对路径")
    sync(parser.parse_args())


if __name__ == "__main__":
    try:
        main()
    except (IssueError, OSError, UnicodeError) as exc:
        print("错误: " + str(exc), file=sys.stderr)
        sys.exit(1)
