# Contributing

Thanks for improving skill-audit! This is a small, zero-dependency tool - contributions
stay small too.

## Ground rules

- **Stdlib only.** No third-party dependencies in `scripts/`.
- **Read-only by design.** Audit scripts must never modify or disable anything.
- **Tests first.** Every behavior change needs a test in `tests/`; run:
  `python tests/test_audit.py && python tests/test_usage.py`
- **Honest docs.** If a heuristic has a known limit, document it in
  `references/methodology.md` instead of overselling the feature.

## Development setup

```bash
git clone https://github.com/Libres-coder/skill-audit
cd skill-audit
python tests/test_audit.py
python tests/test_usage.py
```

Point the scripts at fixture trees for experiments:
`python scripts/audit_skills.py --skills-dir <fixtures> --plugins-dir <fixtures>`.

## Pull requests

1. One concern per PR; describe behavior change and why it matters.
2. Include test evidence (command + output summary) in the PR body.
3. If you add a new detection dimension, document method + threshold + limits in
   `references/methodology.md` and add a fixture test.

## Reporting bugs

Open an issue with: command used, expected vs actual output, OS/Python version, and the
relevant section of `skill-audit-report.md` (redact personal paths if needed).
