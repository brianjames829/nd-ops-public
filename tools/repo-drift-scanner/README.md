# Repo Drift Scanner v0.2

> The archive remembers too much.

Repo Drift Scanner is a small, deterministic Python utility that finds statements which may have become stale after current truth changed.

It is built around a deliberately simple idea:

- **you declare current truth**;
- **you declare source authority**;
- the scanner finds old statements;
- historical material is preserved instead of treated as automatically wrong;
- intentional exceptions can be suppressed without erasing why they were allowed.

No AI model is required. No network service is required. No third-party Python packages are required.

This is a public Nightcoder Designs experiment / utility, not a validated commercial product name.

## What changed in v0.2

v0.2 is an operational-hardening release aimed at making the scanner usable on real repositories repeatedly without becoming noisy.

It adds:

- backward-compatible substring matching plus opt-in `phrase` and `regex` modes;
- rule-specific inline suppressions;
- rule-specific config suppressions with required reasons;
- inspectable suppressed findings;
- one line of review context by default;
- text, JSON, and Markdown reports;
- summary counts by rule and authority;
- `--changed-only` and `--changed-since <ref>` Git modes;
- stricter, human-readable config validation;
- stable automation-oriented exit codes;
- expanded tests.

It still does **not** infer truth, rewrite files, use an LLM, or contact external services.

## Requirements

- Python 3.10+
- Git only when using the Git-aware modes
- zero third-party Python dependencies

## Try the included haunted repository

From this directory:

```bash
python ghost_scan.py examples/demo_repo --config examples/truths.json
```

The demo intentionally contains:

- two stale statements in a current README;
- two legitimate old statements in an archive;
- one config-suppressed migration reference;
- one inline-suppressed old project-name reference.

Expected summary:

```text
CURRENT DRIFT        2
HARMLESS GHOSTS      2
SUPPRESSED           2
HAUNTING SCORE       17  [Whispering]
```

Use `--show-suppressed` to inspect the intentionally suppressed findings:

```bash
python ghost_scan.py examples/demo_repo \
  --config examples/truths.json \
  --show-suppressed
```

## Matching modes

Old v0.1 string patterns still work and mean case-insensitive substring matching:

```json
"stale_patterns": ["MongoDB"]
```

v0.2 also accepts explicit pattern objects.

### Phrase

```json
{
  "value": "API v2",
  "match": "phrase"
}
```

Phrase mode matches the declared phrase without matching it inside a larger word-like token.

### Regex

```json
{
  "value": "Project\\s+Rocket",
  "match": "regex"
}
```

Regex matching is opt-in and case-insensitive. Invalid regex is rejected when the config loads.

Allowed modes:

- `substring`
- `phrase`
- `regex`

No fuzzy or semantic matching is performed.

## Authority rules

Authority rules are evaluated in order. First match wins.

Example:

```json
"authority_rules": [
  {"pattern": "archive/**", "authority": "historical"},
  {"pattern": "ARCHITECTURE.md", "authority": "governing"},
  {"pattern": "README.md", "authority": "current"}
]
```

A stale phrase in `README.md` may therefore become **current drift**, while the same phrase in `archive/2025-plan.md` becomes a **harmless ghost**.

If no authority rule matches, the file is classified as `reference`.

## Suppressions

Suppressions are rule-specific. Suppressing one truth rule does not silence unrelated rules on the same line.

### Inline, same line

```markdown
MongoDB was the previous store. <!-- drift-ignore: database -->
```

### Inline, previous line

```markdown
<!-- drift-ignore: project-name -->
The old Project Rocket name is preserved here for migration context.
```

### Config suppression

```json
"suppressions": [
  {
    "path": "MIGRATION.md",
    "rule_id": "database",
    "reason": "Migration note intentionally names the previous database."
  }
]
```

Config suppressions require a `reason`. The `path` supports the same `fnmatch`-style glob matching used by authority rules.

Suppressed findings retain:

- rule ID;
- source path and line;
- matched text;
- suppression source;
- suppression reason.

They do not contribute to the haunting score or current-drift exit status.

## Context

Human-readable findings include one line before and after the match by default.

```bash
--context 0
--context 1   # default
--context 3
```

## Report formats

### Theatrical terminal output

Default:

```bash
python ghost_scan.py examples/demo_repo --config examples/truths.json
```

### JSON

The v0.1 `--json` flag remains supported:

```bash
python ghost_scan.py examples/demo_repo \
  --config examples/truths.json \
  --json
```

Equivalent explicit form:

```bash
python ghost_scan.py examples/demo_repo \
  --config examples/truths.json \
  --report json
```

JSON always includes suppressed findings so automation can audit them.

### Markdown

```bash
python ghost_scan.py examples/demo_repo \
  --config examples/truths.json \
  --report markdown
```

Include suppression details:

```bash
python ghost_scan.py examples/demo_repo \
  --config examples/truths.json \
  --report markdown \
  --show-suppressed
```

The scanner is side-effect-free by default. It only creates a report file when `--output` is explicitly provided:

```bash
python ghost_scan.py examples/demo_repo \
  --config examples/truths.json \
  --report markdown \
  --output drift-report.md
```

## Open one door

Inspect exactly one repository-relative file:

```bash
python ghost_scan.py examples/demo_repo \
  --config examples/truths.json \
  --door README.md
```

## Git-aware modes

These modes require `root` to be a Git work tree.

### Working-tree changes only

```bash
python ghost_scan.py . \
  --config private-truths.json \
  --changed-only
```

This scans tracked files changed relative to `HEAD` plus untracked files. Deleted files naturally cannot be scanned.

### Files changed since a ref

```bash
python ghost_scan.py . \
  --config private-truths.json \
  --changed-since <commit-or-tag>
```

This uses Git's `REF...HEAD` comparison and scans files returned by that diff.

No remote fetch is performed.

## Config validation

v0.2 rejects common config mistakes before scanning, including:

- missing or duplicate truth IDs;
- empty canonical values;
- missing stale patterns;
- duplicate pattern/mode pairs;
- unknown matching modes;
- malformed regex;
- invalid severity values;
- malformed authority rules;
- duplicate/conflicting authority patterns;
- suppressions without a reason;
- suppressions referencing unknown rule IDs;
- unknown config fields.

Errors are printed plainly instead of dumping a Python traceback for normal config mistakes.

## Exit codes

- `0` — scan completed with no current drift;
- `2` — scan completed and current drift exists;
- `3` — usage, config, Git, or other operational input error.

Historical ghosts and suppressed findings do not cause exit `2` by themselves.

## Haunting score

Only unsuppressed current drift contributes severity points. Historical ghosts and suppressions contribute zero.

```text
0–10     Quiet
11–25    Whispering
26–50    Haunted
51–100   Poltergeist
100+     CALL THE ARCHITECT
```

The theatrical classification is intentionally ridiculous. The score underneath it is deterministic.

## Tests

```bash
python -m unittest discover -s tests -v
```

The v0.2 implementation currently has **29 focused tests** covering authority behavior, matching modes, suppressions, context, reporting, config validation, Git filtering, scan filtering, exit behavior, and scoring.

## Deliberate limitations

v0.2 deliberately does not:

- use an LLM, embeddings, or semantic similarity;
- decide canonical truth automatically;
- rewrite files;
- create commits or pull requests;
- fetch live truth from APIs or the network;
- inspect deep language ASTs;
- provide a plugin framework;
- emit SARIF;
- attempt to become a general documentation linter.

Those belong later only if repeated real-world use proves they solve an actual problem.

## Public/private boundary

The included demo repository is fictional.

Do not publish private rule files, private repository contents, credentials, sensitive internal truth, or restricted source material merely because the public scanner can process it.

The intended ND pattern is:

```text
public scanner
      +
private rules
      +
private repositories
      =
private continuity check
```

The scanner can be public without making the factory public.
