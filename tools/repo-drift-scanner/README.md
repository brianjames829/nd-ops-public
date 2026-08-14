# Repo Drift Scanner v0.3

> The archive remembers too much.

Repo Drift Scanner is a deterministic Python utility for detecting stale repository truth and validating explicit repository contracts.

v0.3 keeps the v0.2 text-drift engine and adds a second layer:

```text
stale text
+ source authority
+ structured state
+ lifecycle rules
+ current-surface rules
+ output ownership
+ append-only history
= repository contract validation
```

No LLM, embeddings, semantic guessing, network service, or third-party Python package is required.

This is a public Nightcoder Designs experiment / utility, not a validated commercial product name.

## What changed in v0.3

v0.2 answered:

> Does a current file still contain text we explicitly declared stale?

v0.3 can also answer:

> Does the repository still satisfy explicit authority, state, lifecycle, ownership, and history contracts?

New deterministic contract types:

1. `authority`
2. `structured_assertion`
3. `lifecycle`
4. `current_surface`
5. `output_ownership`
6. `append_only`

v0.3 also adds:

- `VIOLATION` versus non-blocking `REVIEW` findings;
- optional truth-rule provenance (`canonical_source`, `introduced`, `reason`);
- optional suppression expiration;
- built-in historical conventions for `history/`, `archive/`, `archives/`, `*_LOG.md`, `*_ARCHIVE.md`, and `*_HISTORY.md`;
- explicit authority rules that override those conventions;
- contract findings in text, Markdown, and JSON reports;
- `--contract-baseline <ref>` for append-only Git validation;
- `--no-contracts` for v0.2-style text-only operation;
- `--version`.

It still does **not** infer canonical truth, rewrite files, create commits/PRs, inspect arbitrary program semantics, or decide that two long documents are philosophically inconsistent.

## Requirements

- Python 3.10+
- Git only for Git-aware scan modes and `append_only` contracts
- zero third-party Python dependencies

## Quick start: original haunted demo

The v0.2 demo remains backward-compatible:

```bash
python ghost_scan.py examples/demo_repo --config examples/truths.json
```

Expected core result remains:

```text
CURRENT DRIFT        2
HARMLESS GHOSTS      2
SUPPRESSED           2
HAUNTING SCORE       17  [Whispering]
```

v0.3 adds zero contract findings because the old config contains no contracts.

## Quick start: contract demo

Run the included contract-only example against the same fictional repository:

```bash
python ghost_scan.py examples/demo_repo --config examples/contracts.json
```

It verifies that archived material remains historical and that the README is treated as a current project surface.

## Finding levels

### `VIOLATION`

An explicit deterministic contract is broken.

Examples:

- a historical path is classified `canonical`;
- JSON says `public_product: true` when the declared contract requires `false`;
- a superseded JSONL record is still `active`;
- an undeclared generator references a protected output;
- existing append-only history was modified.

Violations cause exit `2`.

### `REVIEW`

A deterministic signal deserves human judgment, but the scanner does not claim it is objectively wrong.

Examples:

- a current-only surface contains a suspicious old heading;
- an exception/suppression has expired;
- an append-only contract was requested without a baseline.

Review findings do **not** cause exit `2` by themselves.

That distinction is intentional. The scanner should be strict where the repository can state a fact precisely and cautious where interpretation is still required.

# Contract types

## 1. Authority contract

Use when a path or path family has a declared retrieval/continuity role.

```json
{
  "id": "legacy-plans",
  "type": "authority",
  "description": "Legacy plans remain historical",
  "paths": ["archive/**"],
  "must_be": "historical"
}
```

If no file matches, the contract fails by default. Set `"require_match": false` when the path is optional.

Built-in historical conventions apply only when no explicit authority rule matches. Explicit project rules win.

## 2. Structured assertion

Validate an exact JSON value through a JSON Pointer.

```json
{
  "id": "private-product-boundary",
  "type": "structured_assertion",
  "path": "state.json",
  "pointer": "/tesser/public_product",
  "op": "equals",
  "value": false
}
```

Supported operations:

- `equals`
- `not_equals`
- `in`
- `not_in`
- `exists`

This is safer than trying to infer machine state from prose.

## 3. Lifecycle contract

Validate JSONL record invariants.

```json
{
  "id": "no-zombie-opportunities",
  "type": "lifecycle",
  "path": "opportunities.jsonl",
  "record_id_field": "id",
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
      },
      "message": "superseded record still has a live status"
    }
  ]
}
```

The scanner does not invent a lifecycle model. You declare the invariant.

## 4. Current-surface contract

Protect a file whose name/job implies current authority.

```json
{
  "id": "current-state",
  "type": "current_surface",
  "path": "CURRENT_STATE.md",
  "must_be_authority": "current",
  "required_patterns": ["Tesser is private"],
  "forbidden_patterns": ["public Tesser SaaS"],
  "review_patterns": [
    {"value": "^## 2026-05", "match": "regex"}
  ]
}
```

`required_patterns` and `forbidden_patterns` are hard checks.

`review_patterns` generate non-blocking review findings.

All pattern objects support the existing `substring`, `phrase`, and opt-in `regex` modes.

## 5. Output-ownership contract

Protect current/generated artifacts from being claimed by the wrong generator.

```json
{
  "id": "handoff-owner",
  "type": "output_ownership",
  "output": "briefs/latest_handoff.md",
  "inspect": ["scripts/*.py"],
  "owners": ["scripts/build_handoff.py"]
}
```

The scanner searches the explicitly scoped `inspect` files for the protected output reference.

A reference outside the declared owner patterns is a violation.

By default, at least one declared owner must reference the protected output. Disable that with:

```json
"require_owner_reference": false
```

This is deliberately narrower than pretending the scanner can prove arbitrary Python write behavior.

## 6. Append-only contract

Protect ledgers/changelogs where old bytes must not be rewritten.

```json
{
  "id": "changelog-integrity",
  "type": "append_only",
  "path": "CHANGELOG.md"
}
```

Run it with a Git baseline:

```bash
python ghost_scan.py . \
  --config private-rules.json \
  --contract-baseline HEAD
```

Or while comparing a branch/ref:

```bash
python ghost_scan.py . \
  --config private-rules.json \
  --changed-since main
```

`--changed-since` is reused as the append-only baseline unless `--contract-baseline` is supplied explicitly.

The check is intentionally strict:

```text
baseline contents
+ appended bytes
= allowed

existing baseline byte changed/deleted
= violation
```

If no baseline is available, the scanner emits `REVIEW` rather than pretending it verified history.

# Existing text-drift engine

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

Supported:

- `substring`
- `phrase`
- `regex`

No fuzzy or semantic matching.

## Rule provenance

Truth rules may optionally explain where they came from:

```json
{
  "id": "database",
  "description": "Current primary database",
  "canonical": "PostgreSQL",
  "canonical_source": "ARCHITECTURE.md",
  "introduced": "2026-08-14",
  "reason": "Primary persistence layer migrated.",
  "stale_patterns": ["MongoDB"],
  "severity": 10
}
```

Those fields appear in reports so a finding can explain *why the rule exists* instead of merely announcing that Rule 47 is displeased.

## Authority

Rules remain first-match-wins:

```json
"authority_rules": [
  {"pattern": "archive/**", "authority": "historical"},
  {"pattern": "README.md", "authority": "current"}
]
```

v0.3 adds fallback historical conventions for:

```text
history/**
archive/**
archives/**
*_LOG.md
*_ARCHIVE.md
*_HISTORY.md
```

An explicit authority rule always overrides a convention.

## Suppressions

Existing inline and config suppressions remain rule-specific.

Config suppressions may now expire:

```json
{
  "path": "MIGRATION.md",
  "rule_id": "database",
  "reason": "Temporary migration documentation.",
  "expires": "2026-10-01"
}
```

Before expiration, the finding is suppressed.

After expiration, it becomes a non-blocking `REVIEW` signal so someone must decide whether the exception is still legitimate.

# Reports

Supported output remains:

```bash
--report text
--report json
--report markdown
```

The old `--json` alias still works.

Reports now include:

- current drift
- contract violations
- review findings
- historical ghosts
- suppressions
- rule summaries
- authority summaries
- contract-type summaries
- rule/contract provenance where declared

The scanner remains side-effect-free unless `--output` is supplied.

# Git-aware operation

Text scanning still supports:

```bash
--changed-only
```

and:

```bash
--changed-since <ref>
```

No remote fetch is performed.

For a pure v0.2-style pass, skip contracts:

```bash
python ghost_scan.py . --config rules.json --no-contracts
```

# Exit codes

- `0` — completed with no current drift or contract violation;
- `2` — current drift and/or contract violation exists;
- `3` — usage/config/Git/operational input error.

`REVIEW`, historical ghosts, and valid suppressions do not fail the scan by themselves.

# Validation

Before publishing the v0.3 engine, a local development harness ran:

```text
53 tests
53 passed
0 failed
```

That harness covered both v0.2 regression behavior and the new v0.3 contract layer.

The untouched v0.2 fictional demo was also rerun under the v0.3 engine and retained its original result:

```text
CURRENT DRIFT        2
HARMLESS GHOSTS      2
SUPPRESSED           2
HAUNTING SCORE       17  [Whispering]
EXIT CODE            2
```

The repository keeps the prior v0.2 regression suite and adds dedicated v0.3 contract tests.

# Why these contracts exist

The v0.3 contract model came from real continuity failure classes found during a deeper private repository audit after v0.2 surfaced genuine stale-current statements.

The important lesson was that stale truth is not always a sentence.

It can be:

```text
wrong authority
stale JSON state
zombie lifecycle status
wrong current-surface ownership
generator output collision
rewritten historical ledger
```

Those are deterministic problems when the repository explicitly declares the contract.

The public scanner contains only the generic machinery. Private repository rules and private source material remain private.

# Deliberate limitations

v0.3 deliberately does not:

- use an LLM, embeddings, or semantic similarity;
- infer which document is philosophically correct;
- auto-generate canonical truth;
- rewrite files;
- create commits or pull requests;
- contact external services;
- prove arbitrary Python/AST behavior;
- auto-fix lifecycle records;
- treat age alone as proof that a record is stale;
- turn review heuristics into failing violations unless the config explicitly declares them hard contracts.

Ambiguous interpretation belongs above the scanner, in human or bounded reasoning workflows.

# Public/private boundary

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

The scanner can be public without making the factory public.
