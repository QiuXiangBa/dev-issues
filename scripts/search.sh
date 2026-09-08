#!/usr/bin/env bash
# 用法: scripts/search.sh [--in <技术栈>] [--platform <端>] 关键词1 [关键词2 ...]
# 所有关键词都命中的文件才返回。--in 限定目录，--platform 按 frontmatter 的 platform 过滤。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STACK=""; PLATFORM=""; KWS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --in) STACK="$2"; shift 2 ;;
    --platform) PLATFORM="$2"; shift 2 ;;
    *) KWS+=("$1"); shift ;;
  esac
done
[ ${#KWS[@]} -gt 0 ] || [ -n "$PLATFORM" ] || { echo "用法: search.sh [--in 栈] [--platform 端] 关键词..." >&2; exit 1; }
BASE="$ROOT/issues${STACK:+/$STACK}"
[ -d "$BASE" ] || { echo "没有目录: $BASE"; exit 0; }
FILES="$(find "$BASE" -name '*.md' -type f | sort)"
for kw in "${KWS[@]+"${KWS[@]}"}"; do
  [ -n "$FILES" ] || break
  FILES="$(echo "$FILES" | xargs grep -il -- "$kw" 2>/dev/null || true)"
done
if [ -n "$PLATFORM" ] && [ -n "$FILES" ]; then
  FILES="$(echo "$FILES" | xargs grep -il -E "^platform:.*\b$PLATFORM\b" 2>/dev/null || true)"
fi
if [ -z "$FILES" ]; then echo "没有匹配的记录"; exit 0; fi
for f in $FILES; do
  title="$(grep -m1 '^title:' "$f" | sed 's/^title: *//')"
  status="$(grep -m1 '^status:' "$f" | sed 's/^status: *//')"
  tags="$(grep -m1 '^tags:' "$f" | sed 's/^tags: *//')"
  rel="${f#$ROOT/issues/}"
  echo "[$status] $title  ($rel)  $tags"
done
