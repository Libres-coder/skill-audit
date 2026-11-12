#!/usr/bin/env python3
"""skill-audit v3: usage telemetry from Claude Code session transcripts.

Scans ~/.claude/projects/**/*.jsonl and reports which installed pieces
actually get used:

  * MCP servers: tool_use names mcp__<server>__<tool> (app-internal servers
    ccd_*/Claude_Browser are reported separately as "app-internal")
  * Skills: explicit Skill-tool invocations (input.skill) and slash commands
  * Personal skills never invoked (auto-triggered skills do NOT emit tool
    events, so "never invoked" is a hint, not proof - see methodology)

Output: ASCII summary on stderr; UTF-8 markdown report (default
~/.claude/skills/skill-usage-report.md); --json puts ONLY JSON on stdout.

Usage:
  python audit_usage.py [--projects-dir PATH] [--skills-dir PATH]
                        [--output PATH] [--json]
"""
import argparse
import glob
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

HOME = os.path.expanduser("~")
DEFAULTS = {
    "projects": os.path.join(HOME, ".claude", "projects"),
    "skills": os.path.join(HOME, ".claude", "skills"),
    "output": os.path.join(HOME, ".claude", "skills", "skill-usage-report.md"),
}

CMD_RE = re.compile(r"<command-name>/?([^<\s]+)</command-name>")
APP_INTERNAL = {"ccd_turn", "ccd_session_mgmt", "ccd_view", "ccd_session", "Claude_Browser"}


def norm_ts(value):
    """Best-effort timestamp -> 'YYYY-MM-DD HH:MM'. Accepts ISO strings or epoch ms."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            s = value / 1000.0 if value > 1e12 else value
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(s))
        t = str(value)
        m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ]?(\d{2}:\d{2})?", t)
        if m:
            return m.group(0).replace("T", " ")
    except Exception:
        pass
    return None


def scan(projects_dir):
    """Return counters and per-item last-seen data from all transcripts."""
    servers = Counter()
    mcp_tools = Counter()
    skills = Counter()
    commands = Counter()
    last_seen = {}
    sessions_with_mcp = defaultdict(set)
    sessions_scanned = 0
    parse_errors = 0

    for fp in glob.glob(os.path.join(projects_dir, "**", "*.jsonl"), recursive=True):
        sessions_scanned += 1
        session_id = os.path.basename(fp)[:36]
        with open(fp, encoding="utf-8", errors="replace") as f:
            for line in f:
                if "mcp__" not in line and "<command-name>" not in line and '"Skill"' not in line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    parse_errors += 1
                    continue
                ts = norm_ts(ev.get("timestamp") or ev.get("ts"))
                msg = ev.get("message") or {}
                content = msg.get("content")
                if isinstance(content, list):
                    for b in content:
                        if not isinstance(b, dict) or b.get("type") != "tool_use":
                            continue
                        name = b.get("name", "")
                        if name.startswith("mcp__"):
                            parts = name.split("__")
                            server = parts[1] if len(parts) > 1 else "?"
                            servers[server] += 1
                            mcp_tools[name] += 1
                            sessions_with_mcp[server].add(session_id)
                            if ts:
                                last_seen[("mcp", server)] = max(ts, last_seen.get(("mcp", server), ""))
                        elif name == "Skill":
                            sk = (b.get("input") or {}).get("skill")
                            if sk:
                                skills[sk] += 1
                                if ts:
                                    last_seen[("skill", sk)] = max(ts, last_seen.get(("skill", sk), ""))
                elif isinstance(content, str) and "<command-name>" in content:
                    for m in CMD_RE.findall(content):
                        commands[m] += 1
                        if ts:
                            last_seen[("cmd", m)] = max(ts, last_seen.get(("cmd", m), ""))
    return {
        "sessions": sessions_scanned,
        "parse_errors": parse_errors,
        "servers": servers,
        "mcp_tools": mcp_tools,
        "skills": skills,
        "commands": commands,
        "last_seen": last_seen,
        "sessions_with_mcp": sessions_with_mcp,
    }


def personal_skills(skills_dir):
    names = []
    for d in sorted(os.listdir(skills_dir)):
        p = os.path.join(skills_dir, d, "SKILL.md")
        if not os.path.isfile(p):
            continue
        try:
            head = open(p, encoding="utf-8-sig", errors="replace").read(2000)
        except Exception:
            continue
        m = re.search(r"(?m)^name:\s*(\S+)", head)
        names.append(m.group(1) if m else d)
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects-dir", default=DEFAULTS["projects"])
    ap.add_argument("--skills-dir", default=DEFAULTS["skills"])
    ap.add_argument("--output", default=DEFAULTS["output"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    data = scan(args.projects_dir)
    installed = personal_skills(args.skills_dir)

    app_internal = {s: c for s, c in data["servers"].items() if s in APP_INTERNAL}
    real_servers = {s: c for s, c in data["servers"].items() if s not in APP_INTERNAL}
    unused_personal = [n for n in installed if data["skills"].get(n, 0) == 0
                       and data["commands"].get(n, 0) == 0]

    err = sys.stderr
    print("== skill-usage audit %s ==" % time.strftime("%Y-%m-%d %H:%M"), file=err)
    print("transcripts: %d | parse errors: %d" % (data["sessions"], data["parse_errors"]), file=err)
    print("MCP (real servers): %s" % (", ".join("%s=%d" % kv for kv in
                                                sorted(real_servers.items(), key=lambda kv: -kv[1])) or "none"), file=err)
    if app_internal:
        print("app-internal servers: %s" % ", ".join(sorted(app_internal)), file=err)
    print("skill invocations: %s" % (", ".join("%s=%d" % kv for kv in
                                               data["skills"].most_common(10)) or "none"), file=err)
    print("commands: %s" % (", ".join("%s=%d" % kv for kv in
                                      data["commands"].most_common(10)) or "none"), file=err)
    print("personal skills NEVER invoked (hint only): %d/%d" % (len(unused_personal), len(installed)), file=err)
    if unused_personal:
        print("  " + ", ".join(unused_personal[:20]), file=err)

    if args.json:
        rec = getattr(sys.stdout, "reconfigure", None)
        if rec:
            rec(encoding="utf-8")
        print(json.dumps({
            "schema_version": 1,
            "transcripts": data["sessions"],
            "parse_errors": data["parse_errors"],
            "mcp_servers": dict(real_servers),
            "app_internal_servers": dict(app_internal),
            "skill_invocations": dict(data["skills"]),
            "commands": dict(data["commands"]),
            "personal_skills": installed,
            "never_invoked_personal_skills": unused_personal,
        }, ensure_ascii=False))
        return 0

    lines = []
    lines.append("# Skill Usage Report (%s)" % time.strftime("%Y-%m-%d %H:%M"))
    lines.append("")
    lines.append("Transcripts scanned: %d. Parse errors: %d." % (data["sessions"], data["parse_errors"]))
    lines.append("")
    lines.append("## MCP servers actually used")
    if real_servers:
        lines.append("| server | calls | sessions | last seen |")
        lines.append("|---|---|---|---|")
        for s, c in sorted(real_servers.items(), key=lambda kv: -kv[1]):
            lines.append("| %s | %d | %d | %s |" % (s, c, len(data["sessions_with_mcp"].get(s, ())),
                                                    data["last_seen"].get(("mcp", s), "-")))
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## App-internal servers (not user-facing)")
    lines.append(", ".join("%s=%d" % kv for kv in sorted(app_internal.items())) or "(none)")
    lines.append("")
    lines.append("## Skill invocations (explicit Skill tool)")
    if data["skills"]:
        for k, v in data["skills"].most_common():
            lines.append("- %s: %d (last %s)" % (k, v, data["last_seen"].get(("skill", k), "-")))
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## Slash commands")
    if data["commands"]:
        for k, v in data["commands"].most_common():
            lines.append("- /%s: %d (last %s)" % (k, v, data["last_seen"].get(("cmd", k), "-")))
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## Personal skills never invoked (%d/%d)" % (len(unused_personal), len(installed)))
    lines.append("Hint only: auto-triggered skills do not emit tool events. Cross-check with actual behavior.")
    for n in unused_personal:
        lines.append("- %s" % n)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("report written: %s" % args.output, file=err)
    return 0


if __name__ == "__main__":
    sys.exit(main())
