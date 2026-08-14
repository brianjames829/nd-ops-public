# Repo Drift Scanner v0.3.2

> The archive remembers too much.

Repo Drift Scanner is a deterministic Python utility for detecting stale repository truth and validating explicit repository contracts.

v0.3 introduced repository contract validation. v0.3.1 added source-coverage visibility after a real `.rst` miss. v0.3.2 hardens the scanner against **self-reference and evidence-domain mistakes** discovered during external and self-scanning evaluation.

No LLM, embeddings, semantic guessing, network service, or third-party Python package is required.

This is a public Nightcoder Designs experiment / utility, not a validated commercial product name.

For cross-model or maintainer continuity, read **[`AI_HANDOFF.md`](AI_HANDOFF.md)** after this file.

## Why v0.3.2 exists

External use exposed three related self-reference failures:

```text
config contains stale_patterns
+ scanner scans config
= false current drift

previous report contains old finding text
+ scanner scans report
= fixed drift can resurrect

test fixture contains forbidden/stale literal
+ scanner treats fixture as production evidence
= self-reference false positive
```

v0.3.2 fixes the class instead of adding one-off suppressions.

It also closes two source-format gaps found on unrelated repositories:

```text
README.markdown

go.mod
```

## What changed in v0.3.2

### Evidence-domain boundaries

The scanner now distinguishes:

```text
SCANNED
participated in evidence evaluation

IGNORED
known text/source candidate, but unsupported or undecodable

EXCLUDED
intentionally outside this scan's evidence domain
```

That distinction matters. Excluded does not mean historical, harmless, or clean. It means **not evidence for this scan**.

### Active config auto-exclusion

If the active `--config` file is inside the scan root, it is excluded automatically.

This prevents rules like:

```json
"stale_patterns": ["MongoDB"]
```

from accusing their own config file of containing `MongoDB`.

### Active output auto-exclusion

If `--output` points inside the scan root, that active report path is excluded automatically.

This prevents a previous JSON/Markdown/text report from reintroducing stale matched text after the repository itself has been corrected.

### Configurable exclusions

Config files may declare repository-relative glob exclusions:

```json
{
  "exclude_paths": [
    "tests/fixtures/**",
    "generated/**",
    "reports/**"
  ]
}
```

CLI exclusions are also available and repeatable:

```bash
python ghost_scan.py . \
  --config rules.json \
  --exclude 'tests/fixtures/**' \
  --exclude 'generated/**'
```

### Exclusions are visible

Coverage reports now show exclusion boundaries and match counts rather than silently dropping paths.

Example text output:

```text
COVERAGE
SCOPE                 full
FILES DISCOVERED      286
FILES SCANNED         238
FILES IGNORED          42
FILES EXCLUDED           6

EVIDENCE-DOMAIN EXCLUSIONS
auto:config               1  rules.json
config:exclude_paths       5  tests/fixtures/**
```

JSON reports include `coverage.files_excluded` and `coverage.excluded_by_rule`.

Markdown reports include an `Evidence-domain exclusions` table.

### Contract / exclusion conflicts fail loudly

If a direct explicit contract target is also excluded, the configuration fails with exit `3`.

Example:

```text
exclude generated/CURRENT_STATE.md
+
current_surface contract targets generated/CURRENT_STATE.md
=
configuration error
```

The scanner does not guess which instruction wins.

### `.markdown` support

Files such as:

```text
README.markdown
CHANGELOG.markdown
```

are now scanned by the normal stale-truth engine.

### `go.mod` support

`go.mod` is now treated as a supported high-value text surface because it can carry authoritative module/toolchain/dependency state.

## What v0.3.1 added

v0.3.1 was triggered by an external public-repository benchmark where a primary `README.rst` retained an older runtime support statement while package metadata declared a newer support floor.

v0.3.1 added:

- `.rst` scanning
- important extensionless text surfaces
- source-coverage accounting
- ignored-type summaries
- high-value ignored surfaces as non-blocking REVIEW
- format-independent historical `_LOG` / `_ARCHIVE` / `_HISTORY` conventions

## Important extensionless text surfaces

Common high-value extensionless files are scanned when UTF-8 decodable:

```text
README
CHANGELOG
SECURITY
VERSION
CONTRIBUTING
ROADMAP
ARCHITECTURE
```

## Coverage accounting

Every CLI report distinguishes what the scanner discovered from what it actually scanned.

`FILES DISCOVERED` means text/source candidates from a broad candidate-format set, not every binary asset in the repository.

Coverage accounting respects:

- full repository scans
- `--door`
- `--changed-only`
- `--changed-since <ref>`
- configured and CLI evidence-domain exclusions
- active config/output auto-exclusions

### High-value ignored surfaces become REVIEW signals

If a likely authority-bearing text surface is unsupported, the scanner does not call the repository clean and does not invent a violation.

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

An image such as `README.png` is not treated as an ignored text surface merely because its filename begins with README.

## Supported stale-text surfaces

The scanner currently scans these extensions:

```text
.md
.markdown
.rst
.txt
.json
.jsonl
.yaml
.yml
.py
.toml
```

Special supported filename:

```text
go.mod
```

High-value extensionless filenames are listed above.

Other text/source formats may appear in coverage accounting without being stale-text scanned. That is deliberate.

## Core model

```text
text drift
+ source authority
+ structured state
+ lifecycle rules
+ current-surface rules
+ output ownership
+ append-only history
+ source coverage visibility
+ evidence-domain boundaries
= repository continuity validation
```

v0.2-style text rules remain backward-compatible.

## Contract types

The scanner retains six explicit contract types:

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

### Rule quality matters

A broad rule such as:

```text
Python 2
```

can match legitimate narrative like:

```text
dropped support for Python 2
```

Prefer tighter phrases such as:

```text
supports Python 2
requires Python 2
Python 2 is supported
```

Do not add semantic AI merely to rescue sloppy deterministic rules.

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

Important:

```text
authority
!=
exclusion
```

Marking a test fixture `reference` does not remove it from stale-text evaluation. Use `exclude_paths` / `--exclude` when a path is outside the evidence domain.

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

- current drift
- contract violations
- review signals
- historical ghosts
- suppressions
- rule/authority/contract summaries
- declared provenance
- source coverage accounting
- evidence-domain exclusions

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

`--no-contracts` skips configured contracts but still performs text scanning, evidence-boundary handling, and coverage accounting.

## Exit codes

- `0` — completed with no current drift or contract violation
- `2` — current drift and/or contract violation exists
- `3` — usage/config/Git/operational input error

Review signals, historical ghosts, valid suppressions, ignored candidates, and exclusions do not fail a scan by themselves.

## Validation receipts

### v0.3 focused development harness

```text
53 tests
53 passed
0 failed
```

### v0.3.1 focused hardening harness

```text
15 tests
15 passed
0 failed
```

### Current integrated public tree before v0.3.2

An independent outside tester reported:

```text
60 tests
60 passed
0 failed
```

from `python -m unittest discover` on the then-current v0.3.1 public tree.

Keep this separate from the release-specific harness counts.

### v0.3.2 focused development regression

Before publication, the v0.3.2 candidate ran a focused 42-test local set covering:

- prior v0.3 contract behaviors
- prior v0.3.1 `.rst` / coverage / Faker regression behaviors
- active config self-scan prevention
- active output self-poison prevention
- config `exclude_paths`
- CLI `--exclude`
- visible exclusions in JSON/text coverage
- exclude-vs-direct-contract conflict handling
- `.markdown` support
- `go.mod` support
- `--no-contracts` exclusion behavior
- v0.3.2 version reporting

This is a focused development receipt. It is not yet an independent post-publication clone/test receipt.

The original v0.2 haunted-demo behavior remains a backward-compatibility target:

```text
CURRENT DRIFT        2
HARMLESS GHOSTS      2
SUPPRESSED           2
HAUNTING SCORE       17
```

## External evaluation lessons

Small external evaluations have already produced useful classes of evidence:

```text
Faker
→ real README.rst / package-metadata mismatch caught

ty
→ historical alpha wording preserved

Devika
→ ambiguity stayed REVIEW

Requests
→ historical release/version narrative preserved as history; broad rules showed tuning noise

gtop
→ manifest/README support-floor mismatch stayed REVIEW

Redigo
→ README.markdown and go.mod gaps exposed

min-sized-rust
→ unsupported .rs files counted without review spam

nd-ops-public self-scan
→ test fixture self-reference exposed the need for exclusions
```

These are development observations, not a broad statistical precision claim.

## Deliberate limitations

Repo Drift Scanner still does not:

- use an LLM, embeddings, or semantic similarity
- determine philosophical agreement between arbitrary prose documents
- infer canonical truth automatically
- rewrite files
- create commits or pull requests
- contact network services
- prove arbitrary program behavior
- scan every text/source format
- treat an unsupported source type as a hard violation merely because it exists
- guarantee good results from bad rule packs
- prove complex glob-overlap conflicts between every contract pattern and every exclusion pattern

Coverage tells you what the scanner did not inspect. Exclusions tell you what was deliberately outside the evidence domain. Neither should impersonate a clean scan.

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

The public repository contains generic machinery and fictional/public-safe examples. Private Nightcoder Designs truth, private repository contents, and internal Tesser intelligence remain private.

## Continuity / handoff

For another AI model or maintainer, use:

**[`AI_HANDOFF.md`](AI_HANDOFF.md)**

It contains:

- release history
- current architecture
- exact design constraints
- validation boundaries
- external benchmark lessons
- known limitations
- safe change protocol
- next-phase measurement plan
- a copy/paste continuation prompt for ChatGPT, Gemini, Grok, Claude, or another model

## Next phase

After v0.3.2, default to **measurement rather than feature expansion**.

Track across unrelated public repos and the private ND repo set:

```text
true current drift
false current drift
true contract violations
false contract violations
useful reviews
review noise
historical ghosts preserved
high-value coverage misses
suppressions required
repo-specific rules required
```

Let measured failure classes decide whether a later release is justified.
