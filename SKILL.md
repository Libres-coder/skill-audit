---
name: skill-audit
description: "Audit all installed Claude Code skills (personal + plugin) for overlapping triggers, competing always-on styles, and possible conflicting mandates, then produce a remediation plan. Use when the wrong skill fires, when the agent's style feels inconsistent (minimal vs comprehensive), after any skill/plugin install or removal, when many skills were installed and need governance, or when the user asks to audit/check the skills collection (技能审计/冲突/重叠/查重/常开/打架/风格飘忽/治理). Read-only; makes no changes."
---

# Skill Audit

Scan every installed skill for three classes of risk - overlapping triggers, competing
always-on styles, conflicting mandates - and produce a remediation plan.
**Read-only: this skill never modifies or disables anything.** Governance actions are
confirmed by the user first.

## When to use

- After installing a batch of skills/plugins (recommended habit);
- When the wrong skill fires, or the agent's style flips (minimal vs comprehensive);
- When the user asks to audit / find overlaps / check whether skills conflict;
- Periodically, since the collection changes over time.

## Workflow

### 1. Run the audit

```bash
uv run --no-project python ~/.claude/skills/skill-audit/scripts/audit_skills.py
# no uv? plain python works - the script is stdlib-only
```

ASCII summary goes to stderr; the full report is written to
`~/.claude/skills/skill-audit-report.md` (UTF-8).
Options: `--threshold` (default 0.55, lower = more sensitive), `--json` (stdout carries
ONLY JSON, no report file), `--output <path>`, `--skills-dir`, `--plugins-dir`,
`--fail-on always_on|clusters|conflicts` (CI gate), `--save-baseline` / `--baseline`
(delta reporting against a saved snapshot).

### 2. Read the report and handle three risk classes

- **Overlap clusters**: multiple skills in one trigger domain - keep ONE per domain and
  disable the rest (intentional variant pairs inside the same plugin, e.g.
  grill-me/grill-with-docs, usually stay after review);
- **Always-on skills**: should be <= 1. Decide from the actual list the audit prints.
  Note: hook-driven always-on skills (e.g. ponytail's SessionStart hook) are invisible
  to description analysis - check each plugin's hooks manually;
- **Conflict candidates**: minimal and comprehensive styles coexist - the user decides
  which style wins for this project; do not decide for them.

### 3. Usage telemetry (are installed pieces actually used?)

```bash
uv run --no-project python ~/.claude/skills/skill-audit/scripts/audit_usage.py
```

Scans session transcripts and reports: MCP server call counts/sessions/last-seen,
explicit Skill invocations, slash commands, personal skills never invoked, and
**plugins with zero usage** (no MCP calls, no skill invocations, no commands).
Report: `~/.claude/skills/skill-usage-report.md`; `--json` for machines.
**Honest limits**: auto-triggered skills emit no tool events, so "never invoked" is a
hint, not proof; **LSP plugins are passive (they emit no tool calls) and will always
look unused here**; MCP counts cover tool calls, not connection cost. Give newly
installed plugins an observation window before acting. Cross-check with
`claude mcp list` and install dates before declaring dead weight.

### 4. Remediate and re-audit

1. Disable: `claude plugin disable <name>@<marketplace>`; personal skills: delete the
   directory (back it up first);
2. For description edits, follow the skill-creator plugin's trigger-word guidance;
3. **Re-run the audit after remediation** and confirm clusters/always-on counts drop -
   evidence before assertions.

## Hard rules

- Report only; never auto-disable or delete - governance actions need user confirmation;
- Similarity thresholds are heuristics; every cluster is human-reviewed before action
  (see references/methodology.md for limits);
- The report file overwrites the previous one; copy key findings into the conversation
  or PROGRESS before relying on them.
