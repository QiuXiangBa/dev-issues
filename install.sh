#!/usr/bin/env bash
# 一键接入：把知识库放到 ~/dev-issues，注册 Claude Code 的 /issues Skill 和全局规则。
# 用法: git clone https://github.com/QiuXiangBa/dev-issues.git ~/dev-issues && ~/dev-issues/install.sh
set -euo pipefail
REPO_URL="https://github.com/QiuXiangBa/dev-issues.git"
TARGET="$HOME/dev-issues"
CLAUDE_DIR="$HOME/.claude"
HERE="$(cd "$(dirname "$0")" && pwd)"

# 1. 仓库就位
if [ "$HERE" != "$TARGET" ]; then
  if [ -d "$TARGET/.git" ]; then
    echo "已有 $TARGET，执行 pull"
    git -C "$TARGET" pull --rebase --quiet
  elif [ -e "$TARGET" ]; then
    echo "$TARGET 已存在但不是 git 仓库，请先处理" >&2; exit 1
  else
    echo "clone 到 $TARGET"
    git clone --quiet "$REPO_URL" "$TARGET"
  fi
fi

# 2. Skill 软链
mkdir -p "$CLAUDE_DIR/skills"
LINK="$CLAUDE_DIR/skills/issues"
if [ -L "$LINK" ] && [ "$(readlink "$LINK")" = "$TARGET/claude/skills/issues" ]; then
  echo "Skill 已注册"
elif [ -e "$LINK" ]; then
  echo "$LINK 已存在且不是本仓库的软链，请先备份删除" >&2; exit 1
else
  ln -s "$TARGET/claude/skills/issues" "$LINK"
  echo "已注册 Skill: $LINK"
fi

# 3. 全局 CLAUDE.md 规则
RULES="$CLAUDE_DIR/CLAUDE.md"
if [ -f "$RULES" ] && grep -q '^## 问题知识库' "$RULES"; then
  echo "全局规则已存在"
else
  [ -f "$RULES" ] || printf '# 全局规则\n' > "$RULES"
  printf '\n' >> "$RULES"
  cat "$TARGET/claude/CLAUDE.snippet.md" >> "$RULES"
  echo "已写入全局规则: $RULES"
fi

echo
echo "完成。在任意项目打开 Claude Code 输入 /issues 即可使用。"
