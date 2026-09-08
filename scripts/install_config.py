#!/usr/bin/env python3
"""Install the skill symlink and update only our managed CLAUDE.md block."""
from pathlib import Path
import sys

from issues import ROOT, IssueError, atomic_write

BEGIN = "<!-- dev-issues:begin -->"
END = "<!-- dev-issues:end -->"


def configure(home):
    target = ROOT / "claude/skills/issues"
    if not (target / "SKILL.md").is_file():
        raise IssueError("仓库缺少 claude/skills/issues/SKILL.md")
    link = home / ".claude/skills/issues"
    if link.is_symlink():
        if link.resolve() != target.resolve():
            raise IssueError(str(link) + " 指向其他位置（可能已失效），请先备份或移走")
    elif link.exists():
        raise IssueError(str(link) + " 已存在且不是本仓库的软链，请先备份或移走")
    rules = home / ".claude/CLAUDE.md"
    if rules.is_symlink():
        raise IssueError(str(rules) + " 是软链，请在实际配置文件中手动维护受管区块")
    old = rules.read_text(encoding="utf-8") if rules.exists() else "# 全局规则\n"
    snippet = (ROOT / "claude/CLAUDE.snippet.md").read_text(encoding="utf-8").strip()
    block = BEGIN + "\n" + snippet + "\n" + END
    if BEGIN in old or END in old:
        if old.count(BEGIN) != 1 or old.count(END) != 1 or old.index(BEGIN) > old.index(END):
            raise IssueError("CLAUDE.md 的 dev-issues 起止标记损坏，请先修复")
        new = old[:old.index(BEGIN)] + block + old[old.index(END) + len(END):]
    elif snippet in old:
        if old.count(snippet) != 1:
            raise IssueError("发现重复的旧版规则，请先合并")
        new = old.replace(snippet, block, 1)
    elif "## 问题知识库" in old:
        raise IssueError("发现自定义的同名规则。请给原规则加上 " + BEGIN + " 和 " + END + " 后重试；标记内内容将被更新")
    else:
        new = old.rstrip() + "\n\n" + block + "\n"
    if new != old:
        atomic_write(rules, new)
    link.parent.mkdir(parents=True, exist_ok=True)
    if not link.is_symlink():
        link.symlink_to(target, target_is_directory=True)
    print("Skill 已注册，全局规则已更新（保留区块外配置）")


if __name__ == "__main__":
    try:
        configure(Path.home())
    except (IssueError, OSError, UnicodeError) as exc:
        print("错误: " + str(exc), file=sys.stderr)
        sys.exit(1)
