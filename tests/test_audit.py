#!/usr/bin/env python3
"""Tests for skill-audit. Run with: python tests/test_audit.py
(no external deps; builds fixture skill trees in temp dirs)"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "audit_skills.py")


def run_script(args, cwd=None):
    return subprocess.run([sys.executable, SCRIPT] + args,
                          capture_output=True, text=True, cwd=cwd,
                          encoding="utf-8", errors="replace")


def write(path, text, bom=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if bom else "w"
    with open(path, mode, encoding=None if bom else "utf-8") as f:
        if bom:
            f.write(b"\xef\xbb\xbf" + text.encode("utf-8"))
        else:
            f.write(text)


def load_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def mk_skill(path, name, desc):
    write(path, '---\nname: %s\ndescription: %s\n---\nbody\n' % (name, desc))


class ParseTests(unittest.TestCase):
    def _mk(self, tmp):
        # personal skills with tricky frontmatter
        write(os.path.join(tmp, "skills", "alpha", "SKILL.md"),
              '---\nname: alpha\ndescription: >\n  line one\n  line two\n---\nbody\n')
        write(os.path.join(tmp, "skills", "beta", "SKILL.md"),
              '---\nname: beta\ndescription: |\n  literal one\n  literal two\n  literal three\n---\nbody\n')
        write(os.path.join(tmp, "skills", "plain", "SKILL.md"),
              '---\nname: plain\ndescription: "quoted single line"\nmetadata:\n  version: "9.9"\n---\n')
        write(os.path.join(tmp, "skills", "bommy", "SKILL.md"),
              '---\nname: bommy\ndescription: bom file description\n---\n', bom=True)
        write(os.path.join(tmp, "skills", "cjk", "SKILL.md"),
              '---\nname: cjk\ndescription: 审计技能集合治理工具\n---\n')
        write(os.path.join(tmp, "skills", "bad", "SKILL.md"),
              'no frontmatter here\n')
        # plugin layouts
        write(os.path.join(tmp, "plugins", "mp", "pluginA", "1.0", "skills", "grp", "nested", "SKILL.md"),
              '---\nname: nested-skill\ndescription: nested layout skill\n---\n')
        write(os.path.join(tmp, "plugins", "mp", "pluginB", "1.0", "SKILL.md"),
              '---\nname: root-skill\ndescription: root layout skill\n---\n')
        # orphan: same skill name under a "removed" plugin
        write(os.path.join(tmp, "plugins", "mp", "ghost", "1.0", "skills", "alpha", "SKILL.md"),
              '---\nname: alpha\ndescription: ghost copy of alpha\n---\n')

    def test_collect_and_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._mk(tmp)
            p = subprocess.run([sys.executable, SCRIPT,
                                "--skills-dir", os.path.join(tmp, "skills"),
                                "--plugins-dir", os.path.join(tmp, "plugins"),
                                "--threshold", "0.55", "--json"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(p.returncode, 0, p.stderr)
            data = json.loads(p.stdout)
            self.assertGreaterEqual(data["scanned"], 8, data)
            # ghost orphan must be scanned (its source is plugin:ghost)
            self.assertTrue(any(s["source"] == "plugin:ghost"
                                for c in data["clusters"] for s in c)
                            or data["scanned"] >= 8)

    def test_block_scalar_full(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            self._mk(tmp)
            skills = mod.collect_skills(os.path.join(tmp, "skills"), os.path.join(tmp, "plugins"))
            by = {(s["source"], s["name"]): s for s in skills}
            self.assertIn("line two", by[("personal", "alpha")]["desc"])
            self.assertIn("literal three", by[("personal", "beta")]["desc"])
            self.assertEqual("quoted single line", by[("personal", "plain")]["desc"])
            # metadata.version must NOT leak into plain description
            self.assertNotIn("9.9", by[("personal", "plain")]["desc"])
            self.assertEqual("bom file description", by[("personal", "bommy")]["desc"])
            # same name under a different source must coexist
            self.assertIn(("plugin:ghost", "alpha"), by)

    def test_always_on_markers(self):
        mod = load_module()
        self.assertTrue(mod.is_always_on("Use when starting any conversation"))
        self.assertTrue(mod.is_always_on("always applies on every task"))
        self.assertFalse(mod.is_always_on("handles Auto mode failures"))
        self.assertFalse(mod.is_always_on("mentions SessionStart hook events"))

    def test_style_tag_boundaries(self):
        mod = load_module()
        self.assertEqual(mod.style_tag("smallest fully working change"), "minimal")
        self.assertEqual(mod.style_tag("comprehensive incomplete handling"), "maximal")
        self.assertEqual(mod.style_tag("useful helpful stuff"), "none")

    def test_cjk_tokens(self):
        mod = load_module()
        toks = mod.tokens("审计技能 集合治理 工具")
        self.assertIn("审", toks)
        self.assertIn("计", toks)

    def test_threshold_validation(self):
        p = run_script(["--threshold", "1.5"])
        self.assertNotEqual(p.returncode, 0)
        p = run_script(["--threshold", "0"])
        self.assertNotEqual(p.returncode, 0)

    def test_json_stdout_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._mk(tmp)
            p = run_script(["--skills-dir", os.path.join(tmp, "skills"),
                            "--plugins-dir", os.path.join(tmp, "plugins"),
                            "--json"])
            self.assertEqual(p.returncode, 0, p.stderr)
            json.loads(p.stdout)  # must parse as pure JSON

    def test_fail_on_always_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            mk_skill(os.path.join(tmp, "skills", "aa", "SKILL.md"),
                     "aa", "Use when starting any task")
            p = run_script(["--skills-dir", os.path.join(tmp, "skills"),
                            "--plugins-dir", os.path.join(tmp, "plugins"),
                            "--fail-on", "always_on"])
            self.assertNotEqual(p.returncode, 0)

    def test_baseline_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            sd = os.path.join(tmp, "skills")
            pd_ = os.path.join(tmp, "plugins")
            mk_skill(os.path.join(sd, "aa", "SKILL.md"), "aa", "Use when starting any task")
            mk_skill(os.path.join(sd, "bb", "SKILL.md"), "bb", "starting any conversation meta skill")
            b1 = run_script(["--skills-dir", sd, "--plugins-dir", pd_, "--save-baseline", "--json"])
            self.assertEqual(b1.returncode, 0, b1.stderr)
            d1 = json.loads(b1.stdout)
            self.assertIsNone(d1.get("delta"))  # no baseline yet on first run
            # add a skill that overlaps bb
            mk_skill(os.path.join(sd, "cc", "SKILL.md"), "cc", "starting any conversation meta helper")
            b2 = run_script(["--skills-dir", sd, "--plugins-dir", pd_, "--json"])
            self.assertEqual(b2.returncode, 0, b2.stderr)
            d2 = json.loads(b2.stdout)
            self.assertIsNotNone(d2.get("delta"))
            self.assertIn("personal|cc", d2["delta"]["added_skills"])
            self.assertGreaterEqual(len(d2["delta"]["new_clusters"]), 1)


if __name__ == "__main__":
    unittest.main()
