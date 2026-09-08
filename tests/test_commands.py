"""Behavioral regression tests; all mutations and Git remotes are temporary."""
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parent.parent
SAMPLE = "issues/ai-tools/2026-09-08-tool-use-json-truncated.md"


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dev-issues-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "repo with spaces"
        shutil.copytree(SOURCE, self.root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_TERMINAL_PROMPT="0", GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.com",
                        GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.com",
                        GIT_EDITOR="true", GIT_MERGE_AUTOEDIT="no")

    def run_command(self, *args, root=None, ok=True):
        result = subprocess.run(args, cwd=root or self.root, env=self.env,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def command(self, name, *args, **kwargs):
        return self.run_command("bash", "scripts/" + name + ".sh", *args, **kwargs)

    def git(self, *args, **kwargs):
        return self.run_command("git", *args, **kwargs)

    def create(self, slug="sample", title="示例标题", root=None):
        root = root or self.root
        result = self.command("new-issue", "common", slug, title, "test-project", root=root)
        path = Path(result.stdout.strip())
        text = path.read_text(encoding="utf-8")
        text = text.replace("<!-- 粘贴原始报错、复现步骤 -->", "运行命令时出现 Error [demo]。")
        text = text.replace("<!-- 根本原因 -->", "输入格式不符合约定。")
        text = text.replace("<!-- 具体改动，最好附代码片段 -->", "在解析前检查输入格式。")
        path.write_text(text, encoding="utf-8")
        return path.relative_to(root).as_posix()

    def init_remote(self):
        self.command("index")
        self.git("init", "-b", "main")
        self.git("add", ".")
        self.git("commit", "-m", "initial")
        self.remote = self.base / "remote.git"
        self.git("init", "--bare", "--initial-branch=main", str(self.remote))
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "-u", "origin", "main")

    def clone_peer(self):
        peer = self.base / "peer repo"
        self.git("clone", str(self.remote), str(peer))
        return peer


class Commands(Workspace):
    def test_special_characters_round_trip_and_index_escaping(self):
        title = 'A & B | [C] \\ "D": E # F'
        path = self.create(title=title)
        metadata = (self.root / path).read_text().splitlines()[1]
        self.assertEqual(json.loads(metadata.split(": ", 1)[1]), title)
        result = self.command("search", title)
        self.assertIn(title, result.stdout)
        self.command("index")
        index = (self.root / "INDEX.md").read_text()
        self.assertIn("&#124;", index)
        for row in index.splitlines():
            if row.startswith("| "):
                self.assertEqual(row.count("|"), 6)
        self.command("index", "--check")

    def test_new_file_is_exclusive(self):
        path = self.create()
        original = (self.root / path).read_bytes()
        self.command("new-issue", "common", "sample", "replacement", ok=False)
        self.assertEqual((self.root / path).read_bytes(), original)

    def test_invalid_input_does_not_leave_empty_file(self):
        self.command("new-issue", "common", "bad", "bad\nvalue", ok=False)
        self.assertFalse(list((self.root / "issues/common").glob("*.md")))
        self.command("new-issue", "-common", "bad", "title", ok=False)
        self.command("new-issue", "../common", "bad", "title", ok=False)

    def test_literal_search_and_and_semantics(self):
        self.create()
        self.assertIn("示例标题", self.command("search", "[demo]", "error").stdout)
        self.assertIn("没有匹配", self.command("search", "[demo]", "missing").stdout)
        self.assertIn("示例标题", self.command("search", "[").stdout)
        self.command("search", "--", "--unknown")

    def test_search_argument_validation(self):
        self.command("search", "--in", ok=False)
        self.command("search", "--platform", ok=False)
        self.command("search", "--in", "../templates", "解决方案", ok=False)
        self.command("search", "--platform", ".*", ok=False)
        self.command("search", "--unknown", ok=False)
        self.assertIn("tool_use", self.command("search", "--in", "ai-tools").stdout)
        self.assertIn("没有匹配", self.command("search", "--in", "nonexistent").stdout)

    def test_platform_reads_only_frontmatter_and_exact_members(self):
        path = self.create()
        with (self.root / path).open("a") as stream:
            stream.write("\nplatform: [ios]\n")
        self.assertIn("没有匹配", self.command("search", "--platform", "ios").stdout)
        self.assertIn("tool_use", self.command("search", "--platform", "backend").stdout)

    def test_quoted_list_with_comma(self):
        path = self.root / self.create()
        path.write_text(path.read_text().replace("versions: []", 'versions: ["framework 1, build 2", \'tool 3\']'))
        self.command("validate")

    def test_malformed_record_preserves_index_and_search_fails(self):
        path = self.root / self.create()
        path.write_text(path.read_text().replace("status: open", "status: broken"))
        before = (self.root / "INDEX.md").read_bytes()
        self.command("index", ok=False)
        self.assertEqual((self.root / "INDEX.md").read_bytes(), before)
        result = self.command("search", "missing", ok=False)
        self.assertIn("status", result.stderr)
        self.assertNotIn("没有匹配", result.stdout)

    def test_missing_field_cannot_be_read_from_body(self):
        path = self.root / self.create()
        path.write_text(path.read_text().replace("status: open\n", "") + "\nstatus: solved\n")
        self.command("validate", ok=False)

    def test_invalid_schema_variations(self):
        path = self.root / self.create()
        original = path.read_text()
        for old, new in [("status: open", "status: open\nstatus: solved"),
                         ('stack: "common"', "stack: web"),
                         ("platform: []", "platform: [desktop]"),
                         ("tags: []", "tags: [UpperCase]"),
                         ("tags: []", "tags: [one,,two]"),
                         ("versions: []", "versions:\n  - tool 1"),
                         (datetime.date.today().isoformat(), "2026-02-30")]:
            with self.subTest(new=new):
                path.write_text(original.replace(old, new))
                self.command("validate", ok=False)

    def test_symlink_escape_is_rejected(self):
        (self.root / "issues/outside").symlink_to(self.root / "templates", target_is_directory=True)
        self.command("search", "title", ok=False)
        self.command("new-issue", "outside", "escape", "title", ok=False)

    def test_index_staleness_and_empty_library(self):
        self.create()
        self.command("index", "--check", ok=False)
        shutil.rmtree(self.root / "issues")
        (self.root / "issues").mkdir()
        self.command("index")
        self.assertIn("共 0 条", (self.root / "INDEX.md").read_text())


class Synchronization(Workspace):
    def setUp(self):
        super().setUp()
        self.init_remote()

    def test_sync_only_selected_record_and_keeps_untracked_file(self):
        path = self.create()
        draft = self.create("other-draft", "Unpublished draft")
        (self.root / "private-notes.txt").write_text("not part of this operation")
        result = self.command("sync", "--check", path)
        self.assertIn("预检通过", result.stdout)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").stdout.strip(), "1")
        self.command("sync", "-m", "add: example", path)
        files = self.git("ls-tree", "-r", "--name-only", "origin/main").stdout.splitlines()
        self.assertIn(path, files)
        self.assertNotIn("private-notes.txt", files)
        self.assertNotIn(draft, files)
        self.assertNotIn("Unpublished draft", (self.root / "INDEX.md").read_text())
        self.assertEqual((self.root / "private-notes.txt").read_text(), "not part of this operation")
        (self.root / draft).unlink()
        self.command("index", "--check")

    def test_unrelated_staged_or_tracked_edits_are_preserved(self):
        path = self.create()
        readme = self.root / "README.md"
        readme.write_text(readme.read_text() + "\nlocal edit\n")
        self.command("sync", path, ok=False)
        self.git("add", "README.md")
        before = self.git("diff", "--cached").stdout
        self.command("sync", path, ok=False)
        self.assertEqual(self.git("diff", "--cached").stdout, before)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").stdout.strip(), "1")

    def test_empty_template_and_secret_fail_before_commit(self):
        path = Path(self.command("new-issue", "common", "empty", "empty").stdout.strip()).relative_to(self.root).as_posix()
        self.command("sync", path, ok=False)
        (self.root / path).unlink()
        path = self.create()
        secret = "sk-" + "a" * 30
        with (self.root / path).open("a") as stream:
            stream.write("\napi_key = \"" + secret + "\"\n")
        result = self.command("sync", path, ok=False)
        self.assertIn("敏感信息", result.stderr)
        self.assertNotIn(secret, result.stderr)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").stdout.strip(), "1")

    def test_unreviewed_local_commit_is_not_pushed(self):
        path = self.create()
        (self.root / "unrelated.txt").write_text("local")
        self.git("add", "unrelated.txt")
        self.git("commit", "-m", "unrelated")
        result = self.command("sync", path, ok=False)
        self.assertIn("未指定文件", result.stderr)
        self.assertEqual(self.git("rev-list", "--count", "origin/main").stdout.strip(), "1")

    def test_secret_in_earlier_local_commit_cannot_be_hidden_by_later_edit(self):
        path = self.create()
        clean = (self.root / path).read_text()
        (self.root / path).write_text(clean + '\npassword: "actual-value"\n')
        self.git("add", path)
        self.git("commit", "-m", "unsafe")
        (self.root / path).write_text(clean)
        self.command("sync", path, ok=False)
        self.assertEqual(self.git("rev-list", "--count", "origin/main").stdout.strip(), "1")

    def test_fetch_failure_is_not_reported_as_conflict(self):
        path = self.create()
        self.git("remote", "set-url", "origin", str(self.base / "missing.git"))
        result = self.command("sync", path, ok=False)
        self.assertIn("fetch", result.stderr)
        self.assertNotIn("合并冲突", result.stderr)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").stdout.strip(), "1")

    def test_concurrent_additions_regenerate_index(self):
        peer = self.clone_peer()
        local = self.create("local")
        other = self.create("remote", root=peer)
        self.command("sync", other, root=peer)
        self.command("sync", local)
        self.command("index", "--check")
        index = (self.root / "INDEX.md").read_text()
        self.assertIn(local, index)
        self.assertIn(other, index)

    def test_failed_push_retry_resolves_generated_index_conflict(self):
        peer = self.clone_peer()
        local = self.create("local")
        hook = self.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.assertIn("push", self.command("sync", local, ok=False).stderr)
        hook.unlink()
        other = self.create("remote", root=peer)
        self.command("sync", other, root=peer)
        self.command("sync", local)
        self.command("index", "--check")
        index = (self.root / "INDEX.md").read_text()
        self.assertIn(local, index)
        self.assertIn(other, index)

    def test_real_record_conflict_preserves_rebase_for_resolution(self):
        peer = self.clone_peer()
        path = self.root / SAMPLE
        path.write_text(path.read_text().replace("status: solved", "status: open"))
        other = peer / SAMPLE
        other.write_text(other.read_text().replace("status: solved", "status: workaround"))
        self.command("sync", SAMPLE, root=peer)
        result = self.command("sync", SAMPLE, ok=False)
        self.assertIn("记录合并冲突", result.stderr)
        self.assertIn(SAMPLE, self.git("diff", "--name-only", "--diff-filter=U").stdout)
        self.git("rebase", "--abort")
        self.assertIn("status: open", path.read_text())

    def test_deletion_updates_index(self):
        (self.root / SAMPLE).unlink()
        self.command("sync", SAMPLE)
        self.assertIn("共 0 条", (self.root / "INDEX.md").read_text())
        peer = self.clone_peer()
        self.command("index", "--check", root=peer)

    def test_missing_upstream_and_detached_head_fail_before_commit(self):
        path = self.create()
        self.git("branch", "--unset-upstream")
        self.assertIn("upstream", self.command("sync", path, ok=False).stderr)
        self.git("checkout", "--detach")
        self.assertIn("detached HEAD", self.command("sync", path, ok=False).stderr)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").stdout.strip(), "1")

    def test_sensitive_categories_and_placeholders(self):
        path = self.create()
        file = self.root / path
        clean = file.read_text()
        for value in ['Authorization: Bearer ' + 'a' * 20, 'password: "real-value"',
                      'server: 192.168.1.2', 'mail: person@business.test',
                      'phone: ' + '138' + '12345678', 'https://service.internal',
                      '-----BEGIN PRIVATE KEY-----']:
            with self.subTest(value=value[:15]):
                file.write_text(clean + "\n" + value + "\n")
                result = self.command("sync", "--check", path, ok=False)
                self.assertIn("敏感信息", result.stderr)
        file.write_text(clean + '\napi_key: sk-***\npassword: <密码>\nuser@example.com\n10.x.x.x\n')
        self.command("sync", "--check", path)

    def test_sync_requires_explicit_paths(self):
        self.command("sync", ok=False)
        self.command("sync", "old commit message", ok=False)


class Installation(Workspace):
    def configure(self, home, ok=True):
        return self.run_command(sys.executable, "-c",
                                "import sys; from pathlib import Path; sys.path.insert(0, 'scripts'); "
                                "from install_config import configure; configure(Path(sys.argv[1]))", str(home), ok=ok)

    def test_idempotent_install_and_managed_upgrade(self):
        home = self.base / "user home"
        rules = home / ".claude/CLAUDE.md"
        rules.parent.mkdir(parents=True)
        rules.write_text("# Personal\nKeep my preferences.\n")
        self.configure(home)
        first = rules.read_bytes()
        self.configure(home)
        self.assertEqual(rules.read_bytes(), first)
        snippet = self.root / "claude/CLAUDE.snippet.md"
        snippet.write_text(snippet.read_text() + "\n- 新增规则。\n")
        with rules.open("a") as stream:
            stream.write("\n## Other\nKeep this too.\n")
        self.configure(home)
        self.assertIn("新增规则", rules.read_text())
        self.assertIn("Keep my preferences.", rules.read_text())
        self.assertIn("Keep this too.", rules.read_text())
        self.assertTrue((home / ".claude/skills/issues").is_symlink())

    def test_legacy_rules_migrate_once(self):
        home = self.base / "home"
        rules = home / ".claude/CLAUDE.md"
        rules.parent.mkdir(parents=True)
        snippet = (self.root / "claude/CLAUDE.snippet.md").read_text()
        rules.write_text("# Personal\n\n" + snippet)
        self.configure(home)
        self.assertEqual(rules.read_text().count("## 问题知识库"), 1)
        self.assertIn("<!-- dev-issues:begin -->", rules.read_text())

    def test_custom_legacy_rules_are_not_overwritten(self):
        home = self.base / "home"
        rules = home / ".claude/CLAUDE.md"
        rules.parent.mkdir(parents=True)
        original = "## 问题知识库\nMy custom rule.\n"
        rules.write_text(original)
        self.configure(home, ok=False)
        self.assertEqual(rules.read_text(), original)
        self.assertFalse((home / ".claude/skills/issues").exists())

    def test_foreign_broken_symlink_preserved(self):
        home = self.base / "home"
        link = home / ".claude/skills/issues"
        link.parent.mkdir(parents=True)
        link.symlink_to(self.base / "missing")
        self.configure(home, ok=False)
        self.assertTrue(link.is_symlink())
        self.assertFalse((home / ".claude/CLAUDE.md").exists())


if __name__ == "__main__":
    unittest.main()
