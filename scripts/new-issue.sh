#!/usr/bin/env bash
# 用法: scripts/new-issue.sh <技术栈> <slug> "标题" [项目名]
#   技术栈: issues/ 下的目录名，小写，例如 swift flutter uniapp java go ai-tools common。不存在会自动创建。
#   slug:   英文短标识，只允许小写字母、数字、连字符，用作文件名，例如 tool-use-json-truncated
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STACK="${1:?用法: new-issue.sh <技术栈> <slug> \"标题\" [项目名]}"
SLUG="${2:?缺少 slug}"
TITLE="${3:?缺少标题}"
PROJECT="${4:-$(basename "$PWD")}"
[[ "$STACK" =~ ^[a-z0-9-]+$ ]] || { echo "技术栈目录名只能是小写字母、数字、连字符: $STACK" >&2; exit 1; }
[[ "$SLUG" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || { echo "slug 只能是小写字母、数字、连字符，且不能以连字符开头结尾: $SLUG" >&2; exit 1; }
DATE="$(date +%Y-%m-%d)"
DIR="$ROOT/issues/$STACK"
FILE="$DIR/$DATE-$SLUG.md"
[ -e "$FILE" ] && { echo "已存在: $FILE" >&2; exit 1; }
mkdir -p "$DIR"
sed -e "s|{{TITLE}}|$TITLE|" -e "s|{{STACK}}|$STACK|" -e "s|{{PROJECT}}|$PROJECT|" -e "s|{{DATE}}|$DATE|" "$ROOT/templates/issue.md" > "$FILE"
echo "$FILE"
