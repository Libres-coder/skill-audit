# Methodology and known limits

## Detection dimensions and implementation

| Dimension | Method | Threshold / rule |
|---|---|---|
| Overlap triggers | normalize descriptions (lowercase, strip punctuation, keep EN/CN words; CJK split per character) -> SequenceMatcher.ratio + token-set intersection | ratio >= 0.55 AND >= 3 shared tokens -> pair; union-find clusters keyed by (source, name) |
| Always-on styles | action-oriented regex markers (always apply/active, starting any, every task, automatically triggers, use when starting any, auto-start, ...) | any hit -> always-on; self-referential text ("always-on styles", "Auto mode") does not match |
| Style conflicts | cluster members matching minimal words (minimal/simplest/yagni/lazy) vs maximal words (comprehensive/thorough/complete), word-boundary matched | both styles in one cluster -> conflict candidate |
| Delta vs baseline | JSON snapshot of skills/clusters/always-on saved with `--save-baseline`; next run diffs | added/removed skills, new clusters, always-on count change |

## Scan scope

- Personal skills: `~/.claude/skills/<name>/SKILL.md`
- Plugin skills: `~/.claude/plugins/cache/**/SKILL.md` (recursive, any nesting layout;
  plugin name = second path segment)
- Dedupe key: (source, skill name); for duplicate versions the first found wins.
- **Not scanned**: marketplace source dirs (duplicated by cache), commands/agents
  (separate namespaces, different conflict surface).
- **Note**: the cache can retain orphaned copies of uninstalled plugins (a real pua-skills
  remnant was caught this way) - when a cluster points at an unknown source, check
  whether that plugin is still installed; if not, delete the cache directory.

## Known limits (honest disclosure)

1. **Text heuristics, no semantics**: different wording for the same thing -> missed;
   same trigger words with different methods -> over-counted. Every cluster is reviewed
   by a human before action.
2. **English-centric always-on markers**: Chinese "常开/始终" are not in the lexicon
   (v1); Chinese skills need manual review.
3. **Hook-driven always-on skills are invisible**: ponytail activates via SessionStart
   hook and carries no marker in its description - the report covers only the
   description layer; check plugin hooks manually.
4. **Thresholds are empirical**: 0.55 calibrated on an 86-117 skill collection;
   recalibrate when the collection changes significantly.
5. **"Trigger domain" is not "value overlap"**: complementary skills with similar
   descriptions may cluster - the remediation decision belongs to the human.
6. **Conflict detection is a proxy**: real conflicts live in skill bodies; v1
   approximates them with style keywords and will miss cases.
7. **Usage telemetry covers explicit invocations only**: auto-triggered skills emit no
   tool events, and MCP counts exclude connection overhead. Treat "never invoked" as a
   hint and cross-check before disabling anything.

## Remediation patterns

| Situation | Action |
|---|---|
| Same domain, one clearly stronger | disable the weaker one; keep its trigger words in the stronger description |
| Same domain, complementary | add "Not for: X" boundaries to both descriptions (the qa-skills pattern) |
| Always-on count >= 2 | keep one; convert the rest to on-demand via description + disable their hooks |
| Irreconcilable conflict | project-level decision: record the priority in CLAUDE.md |
