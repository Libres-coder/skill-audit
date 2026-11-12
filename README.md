# skill-audit

Audit every installed Claude Code skill for **overlapping triggers**, **competing
always-on styles**, and **possible conflicting mandates** — then produce a
remediation plan. Read-only: it never disables or deletes anything.

When your skill collection grows past ~30 skills (or you mix workflow suites
like superpowers, deepseek-stack, mattpocock-skills), the model faces real
selection noise: three "always-on" working styles competing at session start,
two skills claiming the same trigger domain, minimal-vs-comprehensive style
clashes. skill-audit finds these before they cause wrong behavior.

## Install

Copy this folder into your personal skills directory:

```bash
cp -r skill-audit ~/.claude/skills/
```

Runs on any Python 3.7+ (stdlib only, no dependencies).

## Usage

```bash
python ~/.claude/skills/skill-audit/scripts/audit_skills.py
# ASCII summary on stderr; full UTF-8 report at ~/.claude/skills/skill-audit-report.md

python ~/.claude/skills/skill-audit/scripts/audit_skills.py --json
# stdout carries ONLY a machine-readable JSON array (schema_version: 1)

python ~/.claude/skills/skill-audit/scripts/audit_skills.py --fail-on always_on,clusters
# exit 1 when any listed condition is detected - CI gate
```

Options: `--threshold` (0.55 default; similarity cutoff), `--output <path>`,
`--skills-dir`, `--plugins-dir`, `--skip-network` (n/a, kept for symmetry),
`--fail-on always_on|clusters|conflicts`.

## What it detects

| Category | Method |
|---|---|
| Overlap clusters | normalized description similarity (SequenceMatcher >= 0.55) AND >= 3 shared tokens (CJK split per character); union-find by (source, name) |
| Always-on styles | action-oriented markers: "always apply", "starting any", "every task", "use when starting any", "auto-start", ... |
| Conflict candidates | cluster members mixing minimal words (smallest/yagni/lazy) with maximal words (comprehensive/thorough) |

All heuristics and their known limits are documented in
`references/methodology.md` — read it before acting on a report. Clusters are
candidates for human review, not verdicts.

## Testing

```bash
python tests/test_audit.py   # 8 tests, fixture skill trees, no network
```

## Field record

First deployed on a real 115-skill collection: caught an orphaned plugin cache
(28 leftover SKILL.md files from an uninstalled plugin) and reduced always-on
false positives 3 -> 2 across two calibration rounds. Reviewed independently
(skill-reviewer) and all P0/P1 findings fixed.

## License

MIT
