#!/usr/bin/env python3
"""Tests for audit_usage.py (transcript telemetry). Run: python tests/test_usage.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "audit_usage.py")


def run(args):
    return subprocess.run([sys.executable, SCRIPT] + args,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def mk_skill(path, name, desc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write('---\nname: %s\ndescription: %s\n---\n' % (name, desc))


def append_events(path, events):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def tool_event(name, ts=None, input_=None):
    ev = {"message": {"content": [{"type": "tool_use", "name": name,
                                    "input": input_ or {}}]}}
    if ts:
        ev["timestamp"] = ts
    return ev


def user_event(text, ts=None):
    ev = {"message": {"content": text}}
    if ts:
        ev["timestamp"] = ts
    return ev


class UsageTests(unittest.TestCase):
    def test_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = os.path.join(tmp, "projects")
            skills = os.path.join(tmp, "skills")
            mk_skill(os.path.join(skills, "used-skill", "SKILL.md"), "used-skill", "d")
            mk_skill(os.path.join(skills, "idle-skill", "SKILL.md"), "idle-skill", "d")
            append_events(os.path.join(proj, "p1", "s1.jsonl"), [
                tool_event("Skill", "2026-11-13T01:00:00Z", {"skill": "used-skill"}),
                tool_event("mcp__plugin_github_github__get_me", "2026-11-13T01:01:00Z"),
                tool_event("mcp__ccd_turn__update_plan"),
                user_event("run <command-name>/ponytail:ponytail</command-name>"),
            ])
            append_events(os.path.join(proj, "p1", "s2.jsonl"), [
                tool_event("mcp__plugin_github_github__create_issue", "2026-11-13T02:00:00Z"),
            ])
            with open(os.path.join(proj, "p1", "s3.jsonl"), "w", encoding="utf-8") as f:
                f.write('{"mcp__ broken json\n')

            p = run(["--projects-dir", proj, "--skills-dir", skills,
                     "--output", os.path.join(tmp, "report.md"), "--json"])
            self.assertEqual(p.returncode, 0, p.stderr)
            d = json.loads(p.stdout)
            self.assertEqual(d["schema_version"], 1)
            self.assertEqual(d["transcripts"], 3)
            self.assertGreaterEqual(d["parse_errors"], 1)
            self.assertEqual(d["mcp_servers"].get("plugin_github_github"), 2)
            self.assertIn("ccd_turn", d["app_internal_servers"])
            self.assertEqual(d["skill_invocations"].get("used-skill"), 1)
            self.assertEqual(d["commands"].get("ponytail:ponytail"), 1)
            self.assertIn("idle-skill", d["never_invoked_personal_skills"])
            self.assertNotIn("used-skill", d["never_invoked_personal_skills"])
            # --json deliberately skips the report file (design: stdout is the only output)

    def test_plugin_attribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = os.path.join(tmp, "projects")
            skills = os.path.join(tmp, "skills")
            mk_skill(os.path.join(skills, "a", "SKILL.md"), "a", "d")
            installed = os.path.join(tmp, "installed.json")
            with open(installed, "w", encoding="utf-8") as f:
                json.dump({"plugins": {"github@mp": [{}], "unused-plugin@mp": [{}]}}, f)
            append_events(os.path.join(proj, "p", "s.jsonl"),
                          [tool_event("mcp__plugin_github_github__get_me")])
            out = os.path.join(tmp, "r.md")
            p = run(["--projects-dir", proj, "--skills-dir", skills,
                     "--installed", installed, "--output", out, "--json"])
            self.assertEqual(p.returncode, 0, p.stderr)
            d = json.loads(p.stdout)
            self.assertIn("github", d["used_plugins"])
            self.assertIn("unused-plugin", d["unused_plugins"])
            self.assertNotIn("github", d["unused_plugins"])

    def test_report_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = os.path.join(tmp, "projects")
            skills = os.path.join(tmp, "skills")
            mk_skill(os.path.join(skills, "a", "SKILL.md"), "a", "d")
            append_events(os.path.join(proj, "p", "s.jsonl"),
                          [tool_event("mcp__x__t", "2026-11-13T01:00:00Z")])
            out = os.path.join(tmp, "r.md")
            p = run(["--projects-dir", proj, "--skills-dir", skills, "--output", out])
            self.assertEqual(p.returncode, 0, p.stderr)
            body = open(out, encoding="utf-8").read()
            self.assertIn("MCP servers actually used", body)
            self.assertIn("| x | 1 | 1 |", body)
            self.assertIn("never invoked", body)


if __name__ == "__main__":
    unittest.main()
