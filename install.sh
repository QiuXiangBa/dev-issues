#!/usr/bin/env bash
# 一键接入：把知识库放到 ~/dev-issues，注册 Claude Code 的 /issues Skill 和全局规则。
# 用法: git clone https://github.com/QiuXiangBa/dev-issues.git ~/dev-issues && ~/dev-issues/install.sh
set -euo pipefail
command -v git >/dev/null || { echo "请先安装 git" >&2; exit 1; }
command -v python3 >/dev/null || { echo "请先安装 Python 3.9+" >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else "需要 Python 3.9+")'
REPO_URL="https://github.com/QiuXiangBa/dev-issues.git"
TARGET="$HOME/dev-issues"
HERE="$(cd "$(dirname "$0")" && pwd)"

# 1. 仓库就位
if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
  REPO_ROOT="$(git -C "$TARGET" rev-parse --show-toplevel 2>/dev/null)" || { echo "$TARGET 不是 Git 仓库" >&2; exit 1; }
  [ "$REPO_ROOT" = "$(cd "$TARGET" && pwd -P)" ] || { echo "$TARGET 不是仓库根目录" >&2; exit 1; }
  ORIGIN="$(git -C "$TARGET" remote get-url origin)"
  case "$ORIGIN" in
    https://github.com/QiuXiangBa/dev-issues|https://github.com/QiuXiangBa/dev-issues.git|git@github.com:QiuXiangBa/dev-issues.git|ssh://git@github.com/QiuXiangBa/dev-issues.git) ;;
    *) echo "$TARGET 的 origin 不是 dev-issues，停止安装以免接入错误仓库" >&2; exit 1 ;;
  esac
fi
if [ "$HERE" != "$TARGET" ]; then
  if [ -e "$TARGET/.git" ]; then
    echo "已有 $TARGET，执行 pull"
    git -C "$TARGET" pull --ff-only --quiet
  elif [ -e "$TARGET" ]; then
    echo "$TARGET 已存在但不是 git 仓库，请先处理" >&2; exit 1
  else
    echo "clone 到 $TARGET"
    git clone --quiet "$REPO_URL" "$TARGET"
  fi
fi

# 2–3. 先检查冲突，再更新受管规则和 Skill 软链。
python3 "$TARGET/scripts/install_config.py"

echo
echo "完成。在任意项目打开 Claude Code 输入 /issues 即可使用。"
