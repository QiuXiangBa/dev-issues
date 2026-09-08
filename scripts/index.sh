#!/usr/bin/env bash
# 根据 issues/ 下所有记录的 frontmatter 生成 INDEX.md，按技术栈分组，组内按日期倒序
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/INDEX.md"
field() { grep -m1 "^$2:" "$1" | sed "s/^$2: *//"; }
{
  echo "# 索引"
  echo
  echo "由 \`scripts/index.sh\` 自动生成，不要手改。共 $(find "$ROOT/issues" -name '*.md' -type f | wc -l | tr -d ' ') 条。"
  for dir in $(find "$ROOT/issues" -mindepth 1 -maxdepth 1 -type d | sort); do
    stack="$(basename "$dir")"
    files="$(find "$dir" -name '*.md' -type f | sort -r)"
    [ -n "$files" ] || continue
    echo
    echo "## $stack"
    echo
    echo "| 状态 | 日期 | 标题 | 端 | 标签 |"
    echo "|---|---|---|---|---|"
    for f in $files; do
      rel="issues/$stack/$(basename "$f")"
      printf '| %s | %s | [%s](%s) | %s | %s |\n' \
        "$(field "$f" status)" "$(field "$f" date)" "$(field "$f" title)" "$rel" \
        "$(field "$f" platform | tr -d '[]')" "$(field "$f" tags | tr -d '[]')"
    done
  done
} > "$OUT"
echo "$OUT"
