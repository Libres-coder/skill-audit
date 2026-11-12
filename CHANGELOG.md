# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: SemVer.

## [1.0.0] - 2026-11-13

### Added
- Static audit: overlap clustering (description similarity + shared tokens), always-on
  style detection, minimal-vs-maximal conflict candidates.
- Baseline + delta reporting (`--save-baseline`, `--baseline`): added/removed skills,
  new clusters, always-on changes since the snapshot.
- CI gate mode `--fail-on always_on|clusters|conflicts` (exit 1 on detection).
- Usage telemetry (`audit_usage.py`): MCP server call counts, explicit Skill
  invocations, slash commands, never-invoked personal skills.
- SessionStart guard plugin (silent when healthy, one-line warning on drift).
- Machine-readable JSON output (`schema_version: 1`).
- Field record: orphaned plugin-cache detection (28 leftover SKILL.md files from an
  uninstalled plugin), always-on false positives reduced 3 -> 2 across calibration.

### Fixed
- Full recursive scan: earlier glob patterns missed 55 skills in nested plugin layouts.
- Block-scalar YAML descriptions (`>`, `|`) parsed fully; BOM files read correctly.
- Union-find keyed by (source, name): same-name skills from different sources no longer
  merge.
- Word-boundary matching for style keywords (no more `fully`/`useful` false positives).

### Testing
- 11 tests: parser fixtures (block scalars, BOM, CJK, nested layouts, orphan), gates,
  baseline delta, transcript telemetry.
