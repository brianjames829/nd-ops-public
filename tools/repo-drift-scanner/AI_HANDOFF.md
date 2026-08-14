# Repo Drift Scanner — AI / Maintainer Handoff

Updated: 2026-08-14
Current public version: **v0.3.2**

This file exists so a fresh AI model or human maintainer can continue the scanner without relying on prior chat history.

It is intentionally model-agnostic. It may be handed to ChatGPT, Gemini, Grok, Claude, another coding model, or a human engineer.

## First rule

Treat the current GitHub repository as the source of truth.

Do **not** trust a chat summary, remembered test count, stale search result, or an older model's confidence over a fresh read of the default branch.

Recommended authority order for this public tool:

```text
current default-branch code
→ current scanner README
→ current tests
→ this handoff
→ dated build/validation receipts
→ prior chat summaries
```

If these disagree, inspect the current code and tests before changing anything.

## What the scanner is

Repo Drift Scanner is a deterministic, zero-third-party-runtime-dependency Python utility for repository continuity validation.

It is designed to detect repository state that can be proven wrong from explicit project rules without pretending to understand arbitrary prose semantically.

Current layers:

```text
stale-text rules
+ source authority
+ structured JSON assertions
+ JSONL lifecycle invariants
+ current-surface contracts
+ output-ownership contracts
+ append-only Git contracts
+ source-coverage accounting
+ explicit evidence-domain boundaries
= deterministic repository continuity validation
```

The scanner deliberately does **not** use an LLM, embeddings, semantic similarity, fuzzy inference, automatic rewriting, autonomous PR creation, or network services.

## Core design law

The scanner should only make a hard claim when the project has declared enough structure to prove the claim deterministically.

Use this distinction:

```text
explicit contradiction / broken contract
→ VIOLATION or current drift
→ blocking

ambiguous deterministic signal
→ REVIEW
→ non-blocking

important text/source surface not inspected
→ coverage REVIEW
→ non-blocking

intentionally outside the evidence domain
→ EXCLUDED
→ visible in coverage, not treated as clean/scanned
```

Do not turn REVIEW into a junk drawer, and do not turn ambiguity into a violation merely to produce more findings.

## Release evolution

### v0.2

Established the original deterministic stale-truth scanner:

- substring / phrase / regex matching
- current vs historical authority
- rule-specific suppressions
- context
- text / JSON / Markdown reports
- Git changed-file modes
- stable exit codes
- no AI or network dependency

The fictional haunted demo produced:

```text
CURRENT DRIFT        2
HARMLESS GHOSTS      2
SUPPRESSED           2
HAUNTING SCORE       17
```

### v0.3

Added explicit repository contracts:

1. `authority`
2. `structured_assertion`
3. `lifecycle`
4. `current_surface`
5. `output_ownership`
6. `append_only`

Also added blocking `VIOLATION` vs non-blocking `REVIEW`, rule provenance, expiring suppressions, and built-in historical path/file conventions.

A focused pre-publication development harness recorded **53/53** executions passing.

### v0.3.1

An external public-repository benchmark exposed a silent source-coverage failure: a real `README.rst` contained stale-looking runtime support text, but v0.3 did not scan `.rst`.

v0.3.1 added:

- `.rst` scanning
- high-value extensionless files such as `README`, `VERSION`, and `CHANGELOG`
- coverage accounting
- ignored-type summaries
- non-blocking coverage reviews for high-value unsupported text surfaces
- format-independent `_LOG` / `_ARCHIVE` / `_HISTORY` fallback authority classification

A focused hardening harness recorded **15/15** executions passing.

A separate outside tester later cloned the then-current public tree and reported **60/60** from `python -m unittest discover`. Keep that as a distinct integrated external receipt rather than rewriting the earlier release-specific counts.

### v0.3.2

Further external/self-scanning use exposed a different class of failure: the scanner could consume its own invocation artifacts or test fixtures as evidence.

Observed failure classes:

```text
config contains stale_patterns
→ scanner scans config
→ false current drift

previous report contains old matched text
→ scanner scans old report
→ already-fixed drift resurrects

test fixture contains forbidden/stale literal
→ scanner scans fixture as production evidence
→ self-reference false positive
```

v0.3.2 adds explicit evidence-domain boundaries:

- active `--config` auto-excluded when inside the scan root
- active `--output` auto-excluded when inside the scan root
- config-level `exclude_paths`
- repeatable CLI `--exclude GLOB`
- exclusions visible in coverage reports
- contract evaluation respects the evidence boundary where it enumerates repository files
- explicit direct contract targets that are excluded fail configuration instead of guessing which instruction wins
- `.markdown` support
- `go.mod` support

A local focused v0.3.2 regression set exercised **42 tests** across the v0.3 contract behaviors, v0.3.1 coverage/Faker regression behaviors, and 11 new boundary tests.

After reconstructing the current public test modules together in the local verification tree, an integrated run recorded:

```text
71 tests
71 passed
0 failed
```

Keep those receipts distinct:

```text
v0.3 focused development          53/53
v0.3.1 focused hardening          15/15
external integrated v0.3.1        60/60
v0.3.2 focused development        42/42
v0.3.2 integrated local shape     71/71
```

The 71/71 result is a local integrated verification from the current public code/test surfaces available during the v0.3.2 publishing session. It is **not** an independent third-party fresh-clone receipt of the final post-publication commit. A future external clone/test is therefore still useful evidence rather than redundant ceremony.

## Current module map

```text
ghost_scan.py
    CLI orchestration, exit semantics, report selection, active invocation boundary

drift_core.py
    truth rules, authority, suppressions, matching, supported text surfaces

drift_contracts.py
    six deterministic contract types and contract evaluation

drift_coverage.py
    discovered/scanned/ignored/excluded accounting and high-value coverage reviews

drift_scope.py
    evidence-domain exclusion rules and active config/output boundaries

drift_git.py
    local Git changed-file helpers

drift_report.py
    text / JSON / Markdown rendering

tests/
    regression coverage
examples/
    fictional public-safe demo material
```

## Supported stale-text surfaces

Current supported extensions include:

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

High-value extensionless filenames:

```text
README
CHANGELOG
SECURITY
VERSION
CONTRIBUTING
ROADMAP
ARCHITECTURE
```

Other text/source types can still appear in coverage accounting without being scanned by the stale-text engine.

Do not automatically add every source extension. Add support when repeated real misses justify the parser/maintenance surface.

## Evidence-domain boundaries

This distinction is important:

```text
authority
= what role does this source have if it participates in evidence?

exclusion
= this path does not participate in this scan's evidence domain
```

Do not use `reference` authority as a substitute for exclusion. In the current stale-text engine, anything that is not historical/archive can still become current drift when a stale pattern matches.

### Config exclusions

Example:

```json
{
  "exclude_paths": [
    "tests/fixtures/**",
    "generated/**",
    "reports/**"
  ]
}
```

### CLI exclusions

```bash
python ghost_scan.py . \
  --config rules.json \
  --exclude 'tests/fixtures/**' \
  --exclude 'generated/**'
```

### Automatic invocation exclusions

If the active config or output path is inside the scan root, it is excluded automatically.

These exclusions remain visible in the coverage report. Silence must not impersonate inspection.

### Contract conflict rule

If an explicit direct contract target is also excluded, configuration fails with exit `3`.

Example contradiction:

```text
exclude generated/CURRENT_STATE.md
+
current_surface contract targets generated/CURRENT_STATE.md
=
configuration error
```

Do not silently choose either side.

Current static conflict validation is strongest for direct targets. Complex overlap between globbed authority/output-ownership patterns and globbed exclusions may still require careful rule design and regression tests.

## Rule-quality discipline

The scanner is deterministic. Rule packs can still be bad.

Bad broad rule:

```text
Python 2
```

This can match legitimate current narrative such as:

```text
dropped support for Python 2
```

Prefer narrower claims when the intended stale state is narrower:

```text
supports Python 2
requires Python 2
Python 2 is supported
```

Do not add semantic AI to compensate for a sloppy rule pack.

## External evaluation evidence so far

These are development observations, not a formal statistical benchmark.

### Faker

A public Python repository exposed the original `.rst` blind spot. Current package metadata declared a newer Python support floor while `README.rst` retained an older support statement. After v0.3.1, the scanner caught the mismatch with a rule derived from explicit repository metadata.

An independent outside tester later reproduced the same catch on a fresh clone.

### Requests

An outside tester reported that `HISTORY.md` old Python references were preserved as historical ghosts rather than current drift. Current documentation still produced some rule-dependent noise when broad version phrases were used. Treat that as rule-pack tuning evidence, not a reason to add semantic inference.

### ty

A focused external evaluation preserved old alpha release wording as historical rather than current drift.

### Devika

A successor/current-roadmap tension was intentionally emitted as REVIEW rather than a hard violation because repository evidence did not prove maintainers' intent.

### gtop

README and package manifest exposed a Node support-floor mismatch. It was treated as REVIEW because the repository alone did not prove which side should govern.

### Redigo

`README.markdown` exposed a supported-format gap; `go.mod` exposed a high-value manifest visibility gap. v0.3.2 adds both surfaces.

### min-sized-rust

Rust source files were counted as unsupported candidates without producing one REVIEW per ordinary `.rs` file. This is desired low-noise behavior.

### nd-ops-public self-scan

A test fixture containing a forbidden literal self-triggered. This, plus config self-scan and report self-poisoning reproductions, motivated v0.3.2 evidence-domain boundaries.

## Validation / test commands

From `tools/repo-drift-scanner/`:

```bash
python -m unittest discover -s tests -v
```

Check the version:

```bash
python ghost_scan.py --version
```

Run the fictional demo:

```bash
python ghost_scan.py examples/demo_repo \
  --config examples/truths.json \
  --show-suppressed
```

Expected historical baseline behavior remains conceptually:

```text
2 current drift
2 historical ghosts
2 suppressed
haunting score 17
exit 2
```

If this changes unexpectedly, investigate backward compatibility before accepting a new release.

## Exit codes

```text
0  completed; no current drift / contract violation
2  current drift and/or contract violation
3  usage/config/Git/operational input error
```

REVIEW, historical ghosts, valid suppressions, ignored candidates, and exclusions do not fail a scan by themselves.

## Public/private boundary

This repository contains generic public machinery and fictional/public-safe examples.

Nightcoder Designs private rules, private repository contents, internal strategy, private Tesser intelligence, and sensitive operational data do not belong here.

Intended pattern:

```text
public scanner engine
+
private ND rules/contracts
+
private ND repositories
=
private continuity validation
```

A future model must not publish private rules merely because they would make a benchmark easier to explain.

## Known limitations

Do not claim that the scanner:

- semantically understands arbitrary documentation
- infers canonical truth automatically
- scans every source format
- proves arbitrary program behavior
- has broad measured market precision
- has zero false positives under arbitrary rule packs
- has completed the private ND multi-repository benchmark
- is a validated commercial product

Coverage is candidate-based, not a byte-level census of every binary asset in a repository.

Output paths are normal filesystem paths. A relative `--output` is resolved from the process working directory; use an explicit path when it matters whether the report falls inside the scanned root.

## Current next phase

After v0.3.2, resist feature expansion.

The next high-value work is **measurement**.

Maintain a benchmark ledger with at least:

```text
repository
rules used
current-drift findings
confirmed true drift
confirmed false drift
contract violations
false violations
reviews
useful reviews
review noise
historical ghosts preserved
high-value coverage misses
suppressions required
repo-specific rules required
notes / ambiguity
```

Run this across:

1. unrelated public repositories;
2. the private approved Nightcoder Designs repository set.

The goal is to answer:

- Does the scanner generalize outside ND?
- How much rule setup is required?
- Does precision stay high as rule packs grow?
- Does REVIEW remain useful?
- Which source formats repeatedly cause meaningful misses?
- Which repository structures create recurring ambiguity?

Do not add another contract type merely because a new version number is available at no charge.

## Safe change protocol for a future AI

Before editing:

1. Fresh-read the current default-branch file you intend to change.
2. Read the relevant tests.
3. Reproduce the problem with the smallest fixture possible.
4. Add or update a regression that captures the failure class.
5. Prefer a deterministic fix over a semantic heuristic.
6. Run the focused regression.
7. Run the integrated public test suite.
8. Run the haunted demo.
9. Re-check version/report/exit behavior.
10. Update README + this handoff only after code behavior is settled.
11. Preserve old build receipts as historical evidence; add a new receipt rather than rewriting old numbers.
12. Record limitations as carefully as successes.

Do not reconstruct historical changelogs from memory. Patch or append against a fresh exact source.

## Cross-model continuation prompt

The following block can be pasted into a new model session:

```text
You are continuing work on Nightcoder Designs' public Repo Drift Scanner.

Start with the current GitHub default branch, not prior chat memory.
Repository: brianjames829/nd-ops-public
Scanner path: tools/repo-drift-scanner/

Read in this order:
1. tools/repo-drift-scanner/AI_HANDOFF.md
2. tools/repo-drift-scanner/README.md
3. ghost_scan.py
4. drift_core.py
5. drift_scope.py
6. drift_contracts.py
7. drift_coverage.py
8. current tests

Current intended release is v0.3.2.

Core design constraints:
- deterministic
- zero third-party runtime dependency
- no LLM/embeddings/semantic guessing in the scanner
- hard violations only from explicit provable contracts/rules
- ambiguity stays REVIEW
- history remains history
- exclusions are evidence-domain boundaries, not authority labels
- active config/output must not self-poison scans
- private Nightcoder Designs rules/data stay private

Before changing code, run the current tests and haunted demo. Reproduce any issue with a focused fixture. Preserve backward compatibility unless there is explicit evidence that behavior should change.

After v0.3.2, default to benchmark/measurement work rather than adding new features. Track TP/FP, violation accuracy, review usefulness/noise, historical preservation, coverage misses, suppressions, and rule/setup burden.

Do not claim validation you did not personally reproduce. Distinguish historical release-specific test receipts from a current integrated suite run.
```

## Final handoff state

At this handoff, the engineering direction is:

```text
v0.3 contracts
→ v0.3.1 source-coverage visibility
→ v0.3.2 evidence-domain / self-reference hardening
→ freeze feature expansion
→ measure on external + private real repositories
→ let measured failure classes decide any later release
```

That is where the next maintainer should continue.
