#!/usr/bin/env bash
# 用法: scripts/new-issue.sh <技术栈> "标题" [项目名]
# 技术栈即 issues/ 下的目录名，小写，例如 swift flutter uniapp java go ai-tools common。不存在会自动创建。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STACK="${1:?用法: new-issue.sh <技术栈> \"标题\" [项目名]}"
TITLE="${2:?缺少标题}"
PROJECT="${3:-$(basename "$PWD")}"
if ! [[ "$STACK" =~ ^[a-z0-9-]+$ ]]; then echo "技术栈目录名只能是小写字母、数字、连字符: $STACK" >&2; exit 1; fi
DATE="$(date +%Y-%m-%d)"
SLUG="$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9一-龥]+/-/g; s/^-+|-+$//g' | cut -c1-60)"
DIR="$ROOT/issues/$STACK"
FILE="$DIR/$DATE-$SLUG.md"
if [ -e "$FILE" ]; then echo "已存在: $FILE" >&2; exit 1; fi
mkdir -p "$DIR"
sed -e "s|{{TITLE}}|$TITLE|" -e "s|{{STACK}}|$STACK|" -e "s|{{PROJECT}}|$PROJECT|" -e "s|{{DATE}}|$DATE|" "$ROOT/templates/issue.md" > "$FILE"
echo "$FILE"
