#!/usr/bin/env bash
# 拉取远端，提交本地改动，推送
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
git pull --rebase --quiet || true
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -q -m "${1:-update issues $(date +%Y-%m-%d)}"
fi
git push --quiet
echo "已同步"
