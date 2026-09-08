#!/usr/bin/env python3
"""Knowledge-base commands. Python 3.9+, standard library only.

Frontmatter deliberately supports a small YAML subset: one-line strings and
inline string lists. Quoted strings use JSON double quotes or YAML single quotes.
Unsupported syntax is rejected instead of being silently misinterpreted.
"""
import argparse
import datetime
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
FILE_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md\Z")
PLATFORMS = {"ios", "android", "wechat", "h5", "web", "backend"}
STATUSES = {"solved", "open", "workaround"}
FIELDS = {"title", "stack", "platform", "versions", "tags", "project", "status", "date"}
LIST_FIELDS = {"platform", "versions", "tags"}


class IssueError(Exception):
    pass


def scalar(value):
    value = value.strip()
    if value.startswith('"'):
        try:
            result = json.loads(value)
        except ValueError as exc:
            raise IssueError("双引号字符串必须使用 JSON 转义") from exc
        if not isinstance(result, str):
            raise IssueError("字段必须是字符串")
        return result
    if value.startswith("'"):
        if not re.fullmatch(r"'(?:[^']|'')*'", value):
            raise IssueError("单引号字符串格式错误")
        return value[1:-1].replace("''", "'")
    if (not value or value[0] in "[{&*!|>@`%#" or re.search(r":\s|\s#", value)
            or value.lower() in {"null", "true", "false", "~"}):
        raise IssueError("不支持的未引用字符串，请使用 JSON 双引号")
    return value


def inline_list(value):
    if not (value.startswith("[") and value.endswith("]")):
        raise IssueError("列表必须写成单行 [value, value]，不支持多行 YAML")
    inner = value[1:-1].strip()
    if not inner:
        return []
    # Tokenize without splitting commas inside quoted version names.
    tokens = re.findall(r'''\s*("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^,]+)\s*(,|$)''', inner)
    if "".join(token + sep for token, sep in tokens).replace(" ", "") != inner.replace(" ", ""):
        raise IssueError("列表格式错误")
    if inner.endswith(","):
        raise IssueError("列表不能以逗号结尾")
    return [scalar(token) for token, _ in tokens]


def parse(text, relative):
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise IssueError("文件必须以 --- frontmatter 开始")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise IssueError("frontmatter 缺少结束 ---") from exc
    fields = {}
    for line in lines[1:end]:
        if not line.strip() or line.startswith("#"):
            continue
        match = re.fullmatch(r"([a-z]+):\s*(.*)", line)
        if not match:
            raise IssueError("frontmatter 只支持单行 key: value")
        key, value = match.groups()
        if key not in FIELDS or key in fields:
            raise IssueError("未知或重复字段: " + key)
        fields[key] = inline_list(value) if key in LIST_FIELDS else scalar(value)
    missing = FIELDS - fields.keys()
    if missing:
        raise IssueError("缺少字段: " + ", ".join(sorted(missing)))
    if len(relative.parts) != 3 or relative.parts[0] != "issues":
        raise IssueError("记录必须位于 issues/<技术栈>/<日期>-<slug>.md")
    match = FILE_NAME.fullmatch(relative.name)
    if not match or not NAME.fullmatch(relative.parent.name):
        raise IssueError("目录或文件名格式错误")
    if fields["stack"] != relative.parent.name:
        raise IssueError("stack 与目录不一致")
    try:
        datetime.date.fromisoformat(fields["date"])
    except ValueError as exc:
        raise IssueError("date 必须是有效的 YYYY-MM-DD 日期") from exc
    if fields["date"] != match[1]:
        raise IssueError("date 与文件名日期不一致")
    if fields["status"] not in STATUSES:
        raise IssueError("status 必须是 solved / open / workaround")
    if set(fields["platform"]) - PLATFORMS:
        raise IssueError("platform 含不支持的端")
    if any(not NAME.fullmatch(tag) for tag in fields["tags"]):
        raise IssueError("tags 必须使用小写字母、数字和连字符")
    for key, value in fields.items():
        for item in value if isinstance(value, list) else [value]:
            if not item.strip() or any(ord(c) < 32 for c in item) or "{{" in item:
                raise IssueError(key + " 含空值、控制字符或未替换占位符")
        if isinstance(value, list) and len(set(value)) != len(value):
            raise IssueError(key + " 含重复值")
    return fields


def issue_path(value):
    path = Path(value)
    path = path if path.is_absolute() else ROOT / path
    try:
        relative = path.relative_to(ROOT)
    except ValueError as exc:
        raise IssueError("记录路径必须位于仓库内") from exc
    if len(relative.parts) != 3 or relative.parts[0] != "issues" or not FILE_NAME.fullmatch(path.name) or not NAME.fullmatch(relative.parts[1]):
        raise IssueError("记录路径必须是 issues/<技术栈>/<日期>-<slug>.md")
    if any(parent.is_symlink() for parent in [path, path.parent, ROOT / "issues"]):
        raise IssueError("记录和技术栈目录不支持软链")
    return path


def records(paths=None):
    base = ROOT / "issues"
    if base.is_symlink():
        raise IssueError("issues/ 不支持软链")
    if not base.exists() and not paths:
        return []  # Git does not preserve the directory after the last deletion.
    if base.exists() and not base.is_dir():
        raise IssueError("issues/ 必须是目录")
    if paths is None:
        # Do not follow symlink directories; fail explicitly if one is present.
        paths = []
        for parent, dirs, files in os.walk(base, followlinks=False):
            if any((Path(parent) / name).is_symlink() for name in dirs):
                raise IssueError("issues/ 不支持软链目录")
            paths.extend(Path(parent) / name for name in files if name.endswith(".md"))
    result = []
    for value in sorted(set(paths)):
        path = issue_path(value)
        try:
            text = path.read_text(encoding="utf-8")
            fields = parse(text, path.relative_to(ROOT))
        except (IssueError, OSError, UnicodeError) as exc:
            raise IssueError(str(path.relative_to(ROOT)) + ": " + str(exc)) from exc
        result.append((path, fields, text))
    return result


def atomic_write(path, text, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        if exclusive:
            os.link(name, path)  # Atomic no-clobber creation, including concurrent callers.
        else:
            os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def new_issue(args):
    if not NAME.fullmatch(args.stack) or not NAME.fullmatch(args.slug):
        raise IssueError("技术栈和 slug 只能用小写字母、数字及中间的连字符")
    today = datetime.date.today().isoformat()
    path = issue_path("issues/{}/{}-{}.md".format(args.stack, today, args.slug))
    values = {"TITLE": args.title, "STACK": args.stack, "PROJECT": args.project, "DATE": today}
    template = (ROOT / "templates/issue.md").read_text(encoding="utf-8")
    text = re.sub(r"\{\{(TITLE|STACK|PROJECT|DATE)\}\}",
                  lambda m: json.dumps(values[m[1]], ensure_ascii=False), template)
    parse(text, path.relative_to(ROOT))
    atomic_write(path, text, exclusive=True)
    print(path)


def cell(value):
    # HTML entities keep titles literal in both links and Markdown tables.
    value = html.escape(value, quote=False)
    return re.sub(r"[\\|\[\]`*_]", lambda m: "&#{};".format(ord(m[0])), value)


def index_text(items):
    lines = ["# 索引", "", "由 `scripts/index.sh` 自动生成，不要手改。共 {} 条。".format(len(items))]
    for stack in sorted({fields["stack"] for _, fields, _ in items}):
        lines.extend(["", "## " + stack, "", "| 状态 | 日期 | 标题 | 端 | 标签 |", "|---|---|---|---|---|"])
        group = sorted((item for item in items if item[1]["stack"] == stack),
                       key=lambda item: (item[1]["date"], item[0].name), reverse=True)
        for path, fields, _ in group:
            lines.append("| {} | {} | [{}]({}) | {} | {} |".format(
                fields["status"], fields["date"], cell(fields["title"]), path.relative_to(ROOT).as_posix(),
                cell(", ".join(fields["platform"])), cell(", ".join(fields["tags"]))))
    return "\n".join(lines) + "\n"


def generate_index(check=False, paths=None):
    text = index_text(records(paths))  # Complete validation before touching the old index.
    path = ROOT / "INDEX.md"
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            raise IssueError("INDEX.md 已过期，请运行 scripts/index.sh")
    else:
        atomic_write(path, text)


def search(args):
    if args.stack and not NAME.fullmatch(args.stack):
        raise IssueError("--in 必须是技术栈目录名，不能包含路径")
    if not args.keywords and not args.platform and not args.stack:
        raise IssueError("请提供关键词、--in 或 --platform")
    found = False
    for path, fields, text in records():
        if args.stack and fields["stack"] != args.stack:
            continue
        if args.platform and args.platform not in fields["platform"]:
            continue
        decoded = "\n".join(", ".join(value) if isinstance(value, list) else value for value in fields.values())
        haystack = (text + "\n" + decoded).casefold()
        if all(kw.casefold() in haystack for kw in args.keywords):
            print("[{}] {}  ({})  [{}]".format(fields["status"], fields["title"],
                  path.relative_to(ROOT / "issues").as_posix(), ", ".join(fields["tags"])))
            found = True
    if not found:
        print("没有匹配的记录")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new")
    new.add_argument("stack")
    new.add_argument("slug")
    new.add_argument("title")
    new.add_argument("project", nargs="?", default=Path.cwd().name)
    find = commands.add_parser("search")
    find.add_argument("--in", dest="stack")
    find.add_argument("--platform", choices=sorted(PLATFORMS))
    find.add_argument("keywords", nargs="*")
    index = commands.add_parser("index")
    index.add_argument("--check", action="store_true")
    validate = commands.add_parser("validate")
    validate.add_argument("paths", nargs="*")
    args = parser.parse_args()
    if args.command == "new":
        new_issue(args)
    elif args.command == "search":
        search(args)
    elif args.command == "index":
        generate_index(args.check)
        print("索引一致" if args.check else ROOT / "INDEX.md")
    else:
        print("校验通过，共 {} 条".format(len(records(args.paths or None))))


if __name__ == "__main__":
    try:
        main()
    except (IssueError, OSError, UnicodeError) as exc:
        print("错误: " + str(exc), file=sys.stderr)
        sys.exit(1)
