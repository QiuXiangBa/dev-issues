#!/usr/bin/env bash
# 更新索引，提交本地改动，拉取远端，推送
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
"$ROOT/scripts/index.sh" > /dev/null
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -q -m "${1:-update issues $(date +%Y-%m-%d)}"
fi
if ! git pull --rebase --autostash --quiet; then
  cat >&2 <<'MSG'
拉取时发生冲突。处理方式：
  1. 打开冲突文件，保留两边内容，删掉 <<<<<<< ======= >>>>>>> 标记
  2. git add <文件> && git rebase --continue
  3. 再执行一次 scripts/sync.sh
放弃本次改动：git rebase --abort
MSG
  exit 1
fi
git push --quiet
echo "已同步"
