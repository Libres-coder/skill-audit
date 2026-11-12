#!/usr/bin/env python3
"""skill-audit: detect overlapping triggers, always-on styles, and possible
conflicting mandates across every installed Claude Code skill.

Scans:
  * personal skills:        ~/.claude/skills/<name>/SKILL.md
  * plugin skills:          ~/.claude/plugins/cache/**/SKILL.md (recursive,
                            all layouts; plugin name = second path segment)

Deduplicates by (plugin source, skill name) keeping the first copy found.

Analysis (v1, explainable heuristics - no embeddings):
  1. Overlap clusters: pairs whose normalized descriptions are similar
     (SequenceMatcher ratio >= threshold) AND share at least 3 content tokens
     (CJK text is split per character so Chinese descriptions also participate).
     Clusters are union-find connected components keyed by (source, name).
  2. Always-on styles: descriptions matching action-oriented markers
     ("always apply", "starting any", "every task", "use when starting any",
     "auto-start", etc.).
  3. Conflict candidates: cluster members that prescribe opposite styles
     (minimal/simple vs comprehensive/thorough, word-boundary matched) -
     flagged for human review.

Output:
  * default: ASCII summary on stderr + UTF-8 markdown report file
    (default: skill-audit-report.md next to the skills dir)
  * --json: stdout carries ONLY the machine-readable array (report file skipped)

Usage:
  python audit_skills.py [--skills-dir PATH] [--plugins-dir PATH]
                         [--threshold 0.55] [--output PATH] [--json]
  (No uv? Any Python 3.7+ works: this script is stdlib-only.)
"""
import argparse
import difflib
import glob
import json
import os
import re
import sys
import time

HOME = os.path.expanduser("~")
DEFAULTS = {
    "skills": os.path.join(HOME, ".claude", "skills"),
    "plugins": os.path.join(HOME, ".claude", "plugins", "cache"),
}

ALWAYS_ON_MARKERS = [
    r"always (apply|active|enabled|runs|used)",
    r"starting any",
    r"every (task|conversation|session|request)",
    r"use when starting (any|every)",
    r"automatic(ally)? (active|apply|run|enabled|triggers?)",
    r"on session.?start|at session.?start|every session.?start",
    r"auto.?start|auto.?enable|auto.?trigger",
]
MINIMAL_WORDS = ("minimal", "smallest", "simplest", "yagni", "lazy")
MAXIMAL_WORDS = ("comprehensive", "thorough", "complete", "exhaustive")


def parse_frontmatter(path):
    """Return (name, description) from a SKILL.md, or (None, None).

    Handles YAML block scalars (`description: >` / `|` with indented
    continuation lines). UTF-8 with optional BOM.
    """
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            head = f.read(6000)
    except Exception:
        return None, None
    m = re.match(r"^---\s*\n(.*?)\n---", head, re.S)
    if not m:
        return None, None
    fm = m.group(1)
    name_m = re.search(r"(?m)^name:\s*(\S+)", fm)
    name = name_m.group(1).strip() if name_m else None

    desc_m = re.search(r"(?m)^description:\s*(.*)$", fm)
    if not desc_m:
        return name, None
    value = desc_m.group(1).strip()
    # block scalar: collect indented continuation lines that follow the value line
    if value in (">", "|", ">-", "|-", "> ", "| ") or value.startswith((">", "|")):
        lines = fm.splitlines()
        start = None
        for i, ln in enumerate(lines):
            if ln.strip().startswith("description:"):
                start = i
                break
        parts = []
        if start is not None:
            first = lines[start].split(":", 1)[1].strip().lstrip(">|").strip()
            if first:
                parts.append(first)
            for ln in lines[start + 1:]:
                if not ln or not ln[0].isspace():
                    break  # end of block scalar
                parts.append(ln.strip())
        desc = " ".join(parts).strip()
    else:
        # plain single-line value; strip quotes
        desc = value.strip().strip('"').strip("'")

    return name, (desc or None)


def norm(text):
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9一-鿿]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def tokens(text):
    toks = set(norm(text).split())
    # CJK: whole runs are one token after norm; split per character so
    # Chinese descriptions participate in shared-token counting.
    for t in list(toks):
        if re.search(r"[一-鿿]", t):
            toks.update(re.findall(r"[一-鿿]", t))
    return toks


def collect_skills(skills_dir, plugins_dir):
    """Return list of dicts keyed by (source, name), first copy wins."""
    found = {}
    candidates = []

    if os.path.isdir(skills_dir):
        for d in sorted(os.listdir(skills_dir)):
            p = os.path.join(skills_dir, d, "SKILL.md")
            if os.path.exists(p):
                candidates.append(("personal", d, p))

    if os.path.isdir(plugins_dir):
        for sk in glob.glob(os.path.join(plugins_dir, "**", "SKILL.md"), recursive=True):
            rel = os.path.relpath(os.path.dirname(sk), plugins_dir).split(os.sep)
            plugin = rel[1] if len(rel) >= 2 else "unknown"
            candidates.append(("plugin:" + plugin, os.path.basename(os.path.dirname(sk)), sk))

    for source, dirname, path in candidates:
        name, desc = parse_frontmatter(path)
        if not name or not desc:
            continue
        key = (source, name)
        if key not in found:
            found[key] = {
                "name": name,
                "source": source,
                "dirname": dirname,
                "path": path,
                "desc": desc,
                "norm": norm(desc),
                "toks": tokens(desc),
            }
    return list(found.values())


def detect_overlaps(skills, threshold):
    pairs = []
    n = len(skills)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = skills[i], skills[j]
            common = a["toks"] & b["toks"]
            if len(common) < 3:
                continue
            ratio = difflib.SequenceMatcher(None, a["norm"], b["norm"]).ratio()
            if ratio >= threshold:
                pairs.append((a, b, ratio, common))
    return pairs


def cluster(pairs, skills):
    parent = {(s["source"], s["name"]): (s["source"], s["name"]) for s in skills}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    for a, b, _, _ in pairs:
        union((a["source"], a["name"]), (b["source"], b["name"]))
    groups = {}
    for s in skills:
        groups.setdefault(find((s["source"], s["name"])), []).append(s)
    return [g for g in groups.values() if len(g) > 1]


def is_always_on(desc):
    return any(re.search(m, desc.lower()) for m in ALWAYS_ON_MARKERS)


def style_tag(norm_desc):
    """minimal / maximal / none — word-boundary matched."""
    mn = any(re.search(r"\b%s\b" % w, norm_desc) for w in MINIMAL_WORDS)
    mx = any(re.search(r"\b%s\b" % w, norm_desc) for w in MAXIMAL_WORDS)
    if mn and mx:
        return "mixed"
    if mn:
        return "minimal"
    if mx:
        return "maximal"
    return "none"


def main():
    ap = argparse.ArgumentParser()

    def thresh(v):
        f = float(v)
        if not (0 < f <= 1):
            raise argparse.ArgumentTypeError("threshold must be in (0, 1]")
        return f

    ap.add_argument("--skills-dir", default=DEFAULTS["skills"])
    ap.add_argument("--plugins-dir", default=DEFAULTS["plugins"])
    ap.add_argument("--threshold", type=thresh, default=0.55)
    ap.add_argument("--output", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on", default=None,
                    help="comma-separated gate conditions: always_on, clusters, conflicts; "
                         "exit 1 when any listed condition is detected (for CI)")
    ap.add_argument("--save-baseline", action="store_true",
                    help="after the run, save current state as the baseline for delta reporting")
    ap.add_argument("--baseline", default=None,
                    help="baseline JSON path (default: ~/.claude/skills/.skill-audit-baseline.json)")
    args = ap.parse_args()

    gate = set()
    if args.fail_on:
        valid = {"always_on", "clusters", "conflicts"}
        gate = {g.strip() for g in args.fail_on.split(",") if g.strip()}
        unknown = gate - valid
        if unknown:
            print("--fail-on: unknown condition(s): %s" % ", ".join(sorted(unknown)), file=sys.stderr)
            return 2

    skills = collect_skills(args.skills_dir, args.plugins_dir)
    pairs = detect_overlaps(skills, args.threshold)
    clusters = cluster(pairs, skills)
    always_on = [s for s in skills if is_always_on(s["desc"])]

    conflicts = []
    for grp in clusters:
        styles = {style_tag(s["norm"]) for s in grp}
        if "minimal" in styles and "maximal" in styles:
            conflicts.append(grp)

    # ---- delta vs baseline (continuous mode) ----
    baseline_path = args.baseline or os.path.join(args.skills_dir, ".skill-audit-baseline.json")
    delta = None
    baseline = None
    if os.path.exists(baseline_path):
        try:
            baseline = json.load(open(baseline_path, encoding="utf-8"))
        except Exception:
            baseline = None
    if baseline:
        def keyset(entries):
            return {("%s|%s" % (e.get("source", ""), e.get("name", ""))) for e in entries}
        b_all = keyset(baseline.get("skills", []))
        n_all = keyset([{"source": s["source"], "name": s["name"]} for s in skills])
        b_clusters = {frozenset(sorted(m)) for m in baseline.get("clusters", [])}
        n_clusters = {frozenset(sorted(("%s|%s" % (s["source"], s["name"])) for s in g))
                      for g in clusters}
        b_ao = set(baseline.get("always_on", []))
        n_ao = {("%s|%s" % (s["source"], s["name"])) for s in always_on}
        added = sorted(n_all - b_all)
        removed = sorted(b_all - n_all)
        new_clusters = sorted([sorted(m) for m in (n_clusters - b_clusters)])
        delta = {
            "added_skills": added,
            "removed_skills": removed,
            "new_clusters": new_clusters,
            "always_on_before": len(b_ao),
            "always_on_after": len(n_ao),
            "baseline_at": baseline.get("saved_at", "unknown"),
        }

    if args.save_baseline:
        b = {
            "schema_version": 1,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "skills": [{"source": s["source"], "name": s["name"]} for s in skills],
            "clusters": [[("%s|%s" % (s["source"], s["name"])) for s in g] for g in clusters],
            "always_on": [("%s|%s" % (s["source"], s["name"])) for s in always_on],
        }
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(b, f, ensure_ascii=False, indent=2)
        print("baseline saved: %s" % baseline_path, file=sys.stderr)

    # ---- human summary -> stderr ----
    err = sys.stderr
    print("== skill-audit %s ==" % time.strftime("%Y-%m-%d %H:%M"), file=err)
    print("skills scanned: %d (personal + plugin)" % len(skills), file=err)
    print("overlap pairs (>= %.2f): %d -> clusters: %d" % (args.threshold, len(pairs), len(clusters)), file=err)
    print("always-on style skills: %d" % len(always_on), file=err)
    for s in always_on:
        print("  [always-on] %s (%s)" % (s["name"], s["source"]), file=err)
    print("style-conflict clusters: %d" % len(conflicts), file=err)
    for grp in clusters:
        names = ", ".join("%s(%s)" % (s["name"], s["source"]) for s in grp)
        print("  [overlap] %s" % names, file=err)
    for grp in conflicts:
        names = ", ".join(s["name"] for s in grp)
        print("  [CONFLICT-CANDIDATE] %s" % names, file=err)

    if delta is not None:
        print("-- since baseline (%s) --" % delta["baseline_at"], file=err)
        print("  skills +%d -%d" % (len(delta["added_skills"]), len(delta["removed_skills"])), file=err)
        for c in delta["new_clusters"]:
            print("  new overlap: %s" % ", ".join(c), file=err)
        print("  always-on: %d -> %d" % (delta["always_on_before"], delta["always_on_after"]), file=err)

    if args.json:
        _reconfigure = getattr(sys.stdout, "reconfigure", None)
        if _reconfigure is not None:
            _reconfigure(encoding="utf-8")
        print(json.dumps({
            "schema_version": 1,
            "scanned": len(skills),
            "overlap_pairs": len(pairs),
            "clusters": [[
                {"name": s["name"], "source": s["source"], "path": s["path"]}
                for s in g] for g in clusters],
            "always_on": [{"name": s["name"], "source": s["source"]} for s in always_on],
            "conflicts": [[s["name"] for s in g] for g in conflicts],
            "delta": delta,
        }, ensure_ascii=False))
        # gate evaluation still applies in --json mode
        if ("always_on" in gate and always_on) or \
           ("clusters" in gate and clusters) or \
           ("conflicts" in gate and conflicts):
            return 1
        return 0  # report file skipped in --json mode

    gate_failures = []
    if "always_on" in gate and always_on:
        gate_failures.append("always_on=%d" % len(always_on))
    if "clusters" in gate and clusters:
        gate_failures.append("clusters=%d" % len(clusters))
    if "conflicts" in gate and conflicts:
        gate_failures.append("conflicts=%d" % len(conflicts))
    if gate_failures:
        print("--fail-on gate triggered: %s" % ", ".join(gate_failures), file=sys.stderr)
        return 1

    # ---- full report file ----
    out = args.output or os.path.join(args.skills_dir, "skill-audit-report.md")
    lines = []
    lines.append("# Skill Audit Report (%s)" % time.strftime("%Y-%m-%d %H:%M"))
    lines.append("")
    lines.append("Scanned: %d skills. Threshold: %.2f. Shared-token minimum: 3." % (len(skills), args.threshold))
    lines.append("")
    lines.append("## Always-on style skills (%d)" % len(always_on))
    for s in always_on:
        lines.append("- **%s** (`%s`) — %s" % (s["name"], s["source"], s["desc"][:160]))
    lines.append("")
    lines.append("## Overlap clusters (%d)" % len(clusters))
    pair_by_key = {((a["source"], a["name"]), (b["source"], b["name"])): (r, c)
                   for a, b, r, c in pairs}
    for i, grp in enumerate(clusters, 1):
        lines.append("")
        lines.append("### Cluster %d" % i)
        for s in grp:
            lines.append("- **%s** (`%s`, %s) — %s" % (s["name"], s["source"], s["dirname"], s["desc"][:160]))
        lines.append("")
        lines.append("  Pair evidence (ratio / shared words):")
        for x in range(len(grp)):
            for y in range(x + 1, len(grp)):
                k = ((grp[x]["source"], grp[x]["name"]), (grp[y]["source"], grp[y]["name"]))
                if k in pair_by_key:
                    r, c = pair_by_key[k]
                    lines.append("  - %s <-> %s: %.2f / %s" % (grp[x]["name"], grp[y]["name"], r, ", ".join(sorted(c))))
    lines.append("")
    if delta is not None:
        lines.append("")
        lines.append("## Since baseline (%s)" % delta["baseline_at"])
        lines.append("- skills: +%d / -%d" % (len(delta["added_skills"]), len(delta["removed_skills"])))
        if delta["added_skills"]:
            lines.append("- added: %s" % ", ".join(delta["added_skills"][:20]))
        if delta["removed_skills"]:
            lines.append("- removed: %s" % ", ".join(delta["removed_skills"][:20]))
        for c in delta["new_clusters"]:
            lines.append("- new overlap cluster: %s" % ", ".join(c))
        lines.append("- always-on: %d -> %d" % (delta["always_on_before"], delta["always_on_after"]))
    lines.append("## Style-conflict candidates (%d)" % len(conflicts))
    for i, grp in enumerate(conflicts, 1):
        lines.append("")
        lines.append("### Conflict %d" % i)
        for s in grp:
            lines.append("- **%s** [%s] — %s" % (s["name"], style_tag(s["norm"]), s["desc"][:160]))
    lines.append("")
    lines.append("## Remediation playbook")
    lines.append("1. For each cluster: keep ONE skill per trigger domain; disable the rest")
    lines.append("   (`claude plugin disable <name>@<marketplace>` or delete the personal skill dir).")
    lines.append("2. Always-on skills: at most ONE always-on working style should be active.")
    lines.append("   Judge hook-driven skills (e.g. ponytail's SessionStart hook) manually.")
    lines.append("3. Conflict candidates: human decision - which style wins for this project.")
    lines.append("4. Re-run this audit after any skill/plugin install.")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("report written: %s" % out, file=err)
    return 0


if __name__ == "__main__":
    sys.exit(main())
