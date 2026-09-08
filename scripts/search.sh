#!/usr/bin/env bash
# 用法: scripts/search.sh 关键词1 [关键词2 ...]   所有关键词都命中的文件才返回
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ $# -gt 0 ] || { echo "用法: search.sh 关键词..." >&2; exit 1; }
FILES="$(ls "$ROOT"/issues/*.md 2>/dev/null || true)"
for kw in "$@"; do
  [ -n "$FILES" ] || break
  FILES="$(echo "$FILES" | xargs grep -il -- "$kw" 2>/dev/null || true)"
done
if [ -z "$FILES" ]; then echo "没有匹配的记录"; exit 0; fi
for f in $FILES; do
  title="$(grep -m1 '^title:' "$f" | sed 's/^title: *//')"
  status="$(grep -m1 '^status:' "$f" | sed 's/^status: *//')"
  tags="$(grep -m1 '^tags:' "$f" | sed 's/^tags: *//')"
  echo "[$status] $title  ($(basename "$f"))  $tags"
done
