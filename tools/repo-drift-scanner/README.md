# Repo Drift Scanner v0.3.1

> The archive remembers too much.

Repo Drift Scanner is a deterministic Python utility for detecting stale repository truth and validating explicit repository contracts.

v0.3 introduced repository contract validation. v0.3.1 is a focused source-coverage hardening release driven by an external public-repository benchmark.

No LLM, embeddings, semantic guessing, network service, or third-party Python package is required.

This is a public Nightcoder Designs experiment / utility, not a validated commercial product name.

## Why v0.3.1 exists

An external benchmark against unrelated public repositories exposed a simple but important failure mode:

```text
important source exists
+ scanner does not support that format
= scan may look clean without inspecting the source
```

A public Python project used `README.rst` for its primary documentation. The repository's current package metadata declared a newer Python support floor while that README still described an older one. The v0.3 matching logic could detect the contradiction, but `.rst` was not in the scanner's text-format allowlist, so the file was never inspected.

v0.3.1 fixes that class of failure without responding by scanning every file type indiscriminately.

## What changed in v0.3.1

### reStructuredText support

`.rst` is now scanned by the normal stale-truth engine.

```text
README.rst
CHANGELOG.rst
MIGRATION_HISTORY.rst
```

The built-in historical filename convention is also format-independent now, so names such as:

```text
*_LOG.rst
*_ARCHIVE.rst
*_HISTORY.rst
```

receive the same fallback historical treatment as their Markdown equivalents unless an explicit authority rule overrides it.

### Important extensionless text surfaces

Common high-value extensionless files are now scanned when UTF-8 decodable:

```text
README
CHANGELOG
SECURITY
VERSION
CONTRIBUTING
ROADMAP
ARCHITECTURE
```

### Coverage accounting

Every CLI report now distinguishes what the scanner discovered from what it actually scanned.

Text output includes a section like:

```text
COVERAGE
SCOPE                 full
FILES DISCOVERED      286
FILES SCANNED         241
FILES IGNORED         45

IGNORED BY TYPE
.adoc  2
.cfg   4
.ini   5
.rs    34
```

`FILES DISCOVERED` means text/source candidates from a broad candidate-format set, not every binary asset in the repository.

Coverage accounting respects:

- full repository scans;
- `--door`;
- `--changed-only`;
- `--changed-since <ref>`.

JSON reports include a structured `coverage` object. Markdown reports include a `## Coverage` section.

### High-value ignored surfaces become REVIEW signals

If a likely current/authority-bearing surface is text-like but unsupported, the scanner does not call the repository clean and does not invent a violation.

Example:

```text
README.adoc
```

may produce:

```text
◇ REVIEW SIGNAL

Contract: High-value source coverage [source-coverage]
Type:     coverage
Finding:  high-value repository surface is not scanned by the current text-format allowlist
```

Coverage reviews are non-blocking. They do not cause exit `2` by themselves.

This is the intended distinction:

```text
explicit contract broken
→ VIOLATION
→ blocking

important source was not inspected
→ REVIEW
→ non-blocking human judgment
```

An image such as `README.png` is not treated as an ignored text surface merely because its filename begins with README.

## Supported text surfaces

The stale-truth scanner currently scans these extensions:

```text
.md
.rst
.txt
.json
.jsonl
.yaml
.yml
.py
.toml
```

It also scans the high-value extensionless filenames listed above.

Other text/source formats may appear in coverage accounting without being scanned by the stale-text engine. That is deliberate. v0.3.1 exposes the gap rather than silently widening the parser surface based on imagination.

## Core model

The scanner now has two deterministic layers:

```text
text drift
+ source authority
+ structured state
+ lifecycle rules
+ current-surface rules
+ output ownership
+ append-only history
+ source coverage visibility
= repository continuity validation
```

v0.2-style text rules remain backward-compatible.

## Contract types

v0.3 retains six explicit contract types:

1. `authority`
2. `structured_assertion`
3. `lifecycle`
4. `current_surface`
5. `output_ownership`
6. `append_only`

### 1. Authority

```json
{
  "id": "legacy-plans",
  "type": "authority",
  "paths": ["archive/**"],
  "must_be": "historical"
}
```

Use when a path family has an explicit retrieval/continuity role.

### 2. Structured assertion

```json
{
  "id": "private-product-boundary",
  "type": "structured_assertion",
  "path": "state.json",
  "pointer": "/system/public_product",
  "op": "equals",
  "value": false
}
```

Supported operations:

```text
equals
not_equals
in
not_in
exists
```

### 3. Lifecycle

```json
{
  "id": "no-zombies",
  "type": "lifecycle",
  "path": "opportunities.jsonl",
  "invariants": [
    {
      "when": {
        "field": "superseded_by",
        "op": "exists",
        "value": true
      },
      "require": {
        "field": "status",
        "op": "not_in",
        "value": ["active", "pending", "open"]
      }
    }
  ]
}
```

The scanner validates declared lifecycle logic; it does not invent the lifecycle.

### 4. Current surface

```json
{
  "id": "current-state",
  "type": "current_surface",
  "path": "CURRENT_STATE.md",
  "must_be_authority": "current",
  "required_patterns": ["Current state"],
  "forbidden_patterns": ["superseded active plan"],
  "review_patterns": [
    {"value": "^## 2025-", "match": "regex"}
  ]
}
```

Required/forbidden patterns are hard checks. Review patterns remain non-blocking.

### 5. Output ownership

```json
{
  "id": "handoff-owner",
  "type": "output_ownership",
  "output": "briefs/latest_handoff.md",
  "inspect": ["scripts/*.py"],
  "owners": ["scripts/build_handoff.py"]
}
```

This catches protected current outputs being referenced by undeclared generators without pretending to prove arbitrary program semantics.

### 6. Append only

```json
{
  "id": "changelog-integrity",
  "type": "append_only",
  "path": "CHANGELOG.md"
}
```

Evaluate with a Git baseline:

```bash
python ghost_scan.py . \
  --config rules.json \
  --contract-baseline HEAD
```

Existing baseline bytes may not be rewritten; new bytes may be appended.

Without a baseline the scanner emits REVIEW rather than claiming history was verified.

## Matching modes

Backward-compatible string patterns remain case-insensitive substring checks:

```json
"stale_patterns": ["MongoDB"]
```

Explicit modes:

```json
{"value": "API v2", "match": "phrase"}
```

```json
{"value": "Project\\s+Rocket", "match": "regex"}
```

No fuzzy or semantic matching is performed.

## Rule provenance

Truth rules can explain where they came from:

```json
{
  "id": "runtime-floor",
  "description": "Current runtime support floor",
  "canonical": "Python >= 3.10",
  "canonical_source": "setup.py",
  "reason": "Packaging metadata declares python_requires >=3.10.",
  "stale_patterns": ["Python 3.8 and above"],
  "severity": 10
}
```

Reports retain that provenance.

## Authority conventions

Explicit authority rules are first-match-wins and override built-in conventions.

Fallback historical conventions include:

```text
history/**
archive/**
archives/**
*_LOG.<supported text format>
*_ARCHIVE.<supported text format>
*_HISTORY.<supported text format>
```

## Suppressions

Inline and config suppressions remain rule-specific.

Config suppressions may expire:

```json
{
  "path": "MIGRATION.md",
  "rule_id": "database",
  "reason": "Temporary migration documentation.",
  "expires": "2026-10-01"
}
```

Expired suppressions become non-blocking REVIEW signals.

## Reports

Supported formats:

```bash
--report text
--report json
--report markdown
```

The legacy `--json` alias remains available.

Reports include:

- current drift;
- contract violations;
- review signals;
- historical ghosts;
- suppressions;
- rule/authority/contract summaries;
- declared provenance;
- source coverage accounting.

The scanner remains side-effect-free unless `--output` is explicitly supplied.

## Git-aware operation

```bash
--changed-only
```

and:

```bash
--changed-since <ref>
```

No remote fetch is performed.

`--no-contracts` skips configured contracts but still performs text scanning and coverage accounting.

## Exit codes

- `0` — completed with no current drift or contract violation;
- `2` — current drift and/or contract violation exists;
- `3` — usage/config/Git/operational input error.

Review signals, historical ghosts, and valid suppressions do not fail a scan by themselves.

## Validation

### v0.3 baseline

Before v0.3 publication, a focused development harness ran:

```text
53 tests
53 passed
0 failed
```

### v0.3.1 hardening

The source-coverage changes were then exercised through a separate focused regression harness:

```text
15 tests
15 passed
0 failed
```

The v0.3.1 harness covered:

- `.rst` scanning;
- extensionless `README` and `VERSION` scanning;
- format-independent historical filename conventions;
- coverage counts;
- ignored-type summaries;
- high-value unsupported text surfaces;
- binary README-like files not becoming false coverage reviews;
- `--door`/filtered coverage behavior;
- JSON/Markdown/text coverage rendering;
- replay of the external `.rst` documentation miss;
- preservation of the original v0.2 haunted-demo behavior.

The original v0.2 behavior remains:

```text
CURRENT DRIFT        2
HARMLESS GHOSTS      2
SUPPRESSED           2
HAUNTING SCORE       17
```

## External benchmark lesson

The first small external benchmark was intentionally conservative. It showed three useful behaviors:

```text
historical release text
→ preserved as history

ambiguous roadmap/current-state tension
→ REVIEW, not fake certainty

important unsupported README.rst
→ exposed a source-coverage blind spot
```

v0.3.1 addresses the third result.

It does not turn that tiny benchmark into a broad precision claim.

## Deliberate limitations

Repo Drift Scanner still does not:

- use an LLM, embeddings, or semantic similarity;
- determine philosophical agreement between arbitrary prose documents;
- infer canonical truth automatically;
- rewrite files;
- create commits or pull requests;
- contact network services;
- prove arbitrary program behavior;
- scan every text/source format;
- treat an unsupported source type as a hard violation merely because it exists.

Coverage tells you what the scanner did not inspect. It does not pretend those files are wrong.

## Public/private boundary

The intended pattern remains:

```text
public scanner
      +
private rules/contracts
      +
private repositories
      =
private continuity validation
```

The public repository contains generic machinery and fictional examples. Private truth and private repository content remain private.
