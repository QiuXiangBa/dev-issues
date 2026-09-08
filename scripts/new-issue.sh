#!/usr/bin/env bash
# 用法: scripts/new-issue.sh "标题" [项目名]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TITLE="${1:?用法: new-issue.sh \"标题\" [项目名]}"
PROJECT="${2:-$(basename "$PWD")}"
DATE="$(date +%Y-%m-%d)"
SLUG="$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9一-龥]+/-/g; s/^-+|-+$//g' | cut -c1-60)"
FILE="$ROOT/issues/$DATE-$SLUG.md"
if [ -e "$FILE" ]; then echo "已存在: $FILE" >&2; exit 1; fi
sed -e "s|{{TITLE}}|$TITLE|" -e "s|{{PROJECT}}|$PROJECT|" -e "s|{{DATE}}|$DATE|" "$ROOT/templates/issue.md" > "$FILE"
echo "$FILE"
