# Nightcoder Designs — Public Proof

Updated: 2026-08-14

This repository contains curated, sanitized proof from Nightcoder Designs systems work.

It is **not** the private source of truth and it is not a mirror of internal repositories. The goal is simpler: publish enough real engineering evidence that a reader can understand what was built, what constraint mattered, what was learned, and what remains unproven.

Private Nightcoder Designs repositories remain authoritative for internal state.

---

## Start Here

### Runnable: Repo Drift Scanner v0.3.2

[`tools/repo-drift-scanner/`](./tools/repo-drift-scanner/)

A deterministic Python utility for stale-truth detection, explicit repository contracts, source coverage, and evidence-domain boundaries without using an LLM.

Current capabilities include:

- authority contracts
- structured JSON assertions
- JSONL lifecycle invariants
- current-surface contracts
- generated-output ownership
- append-only Git history
- blocking `VIOLATION` versus non-blocking `REVIEW`
- rule provenance
- expiring suppressions
- built-in historical path/file conventions
- text / JSON / Markdown reports
- `--changed-only` and `--changed-since <ref>`
- source-coverage accounting
- `.rst` and `.markdown` scanning
- important extensionless text surfaces
- `go.mod` support
- active config/output self-exclusion
- config `exclude_paths` and repeatable CLI `--exclude`
- visible evidence-domain exclusions in coverage reports
- zero model/API/runtime-package dependencies

v0.3.2 was driven by real self-reference failures found during external/self-scanning use: config files, prior scanner reports, and test fixtures could otherwise become false evidence. The new boundary model distinguishes **scanned**, **ignored**, and **excluded** rather than letting silence impersonate inspection.

The scanner includes a public cross-model continuity file:

[`tools/repo-drift-scanner/AI_HANDOFF.md`](./tools/repo-drift-scanner/AI_HANDOFF.md)

That handoff is written so a fresh ChatGPT, Gemini, Grok, Claude, other model, or human maintainer can continue from the current GitHub state without prior conversation history.

Validation receipts are kept distinct by release. A focused v0.3 harness recorded 53/53, v0.3.1 hardening recorded 15/15, an independent tester reported 60/60 on the then-current integrated v0.3.1 public tree, and the v0.3.2 development verification expanded to the current 71-test public regression shape locally. See the scanner README/handoff for exact boundaries and caveats.

The interface is deliberately stranger than the machinery. The scanner only claims violations where the repository declares deterministic evidence; ambiguity and incomplete coverage remain review signals instead of pretending certainty.

### Tesser v0.2 Repository Ingestion Spine

[`TESSER_INGESTION_SPINE_CASE.md`](./TESSER_INGESTION_SPINE_CASE.md)

A sanitized engineering case study covering:

- model-independent source ingestion
- explicit approved-source boundaries
- local Git and read-only GitHub adapters
- provenance and content hashing
- authority / privacy classification
- deterministic chunking
- CLI manifest output
- unit-test / validation state
- deliberate non-goals and current limitations

Tesser is private Nightcoder Designs intelligence infrastructure. The case study documents the engineering work without publishing private memory or runtime data.

### Monitoring & Edge Security Alignment

[`MONITORING_EDGE_ALIGNMENT_CASE.md`](./MONITORING_EDGE_ALIGNMENT_CASE.md)

A production reliability case covering false-positive uptime alerts caused by an edge-security interaction, root-cause analysis, targeted corrective controls, and post-change validation.

### Production / Proof Architecture

[`ARCHITECTURE_OVERVIEW.md`](./ARCHITECTURE_OVERVIEW.md)

A high-level public-safe overview of the live web environment and the private-to-public proof workflow.

### Product / Service Proof Evolution

[`PRODUCT_SERVICE_PROOF_NOTE.md`](./PRODUCT_SERVICE_PROOF_NOTE.md)

A public-safe record of how internal documentation and operations work became reusable product/service infrastructure.

For the complete index, see [`ARTIFACT_INDEX.md`](./ARTIFACT_INDEX.md).

---

## What Belongs Here

Public artifacts may cover real, sanitized work in areas such as:

- systems architecture
- reliability / monitoring
- AI and model-independent knowledge systems
- data / provenance / retrieval architecture
- automation and agents
- Base / Ethereum / Web3 experiments
- APIs / developer tooling
- security
- mechatronics / physical-system integration
- product and operational systems

The standard is **finished enough to demonstrate something real**.

Architecture speculation by itself is not public proof.

---

## Public-Proof Standard

A useful artifact should answer:

1. What problem or system was being addressed?
2. What constraints mattered?
3. What was actually implemented, tested, operated, or observed?
4. What result or validation exists?
5. What remains incomplete or unproven?
6. What reusable lesson came from the work?
7. What details were intentionally omitted for safety?

Quality matters more than artifact count.

---

## Private / Public Boundary

This repository intentionally excludes:

- credentials / secrets / tokens
- private keys / seed phrases
- sensitive wallet or account identifiers
- private customer/client records
- raw private logs
- private dashboards
- private ND strategy or memory
- unsanitized prompts/context
- detailed controls that materially increase attack risk
- bank/payment records
- private source material simply because it exists

See [`PUBLICATION_POLICY.md`](./PUBLICATION_POLICY.md) for the publication and sanitization rules.

---

## Tesser Boundary

Tesser is **private Nightcoder Designs intelligence infrastructure**.

It is not a public SaaS, public chatbot, public Base explorer, scanner suite, token, or public product brand.

Nightcoder Designs may publish sanitized engineering lessons, case studies, tests, demos, or separate public products derived from capabilities developed internally. Those public artifacts must not expose private Tesser memory, strategy, permissions, or restricted runtime state.

---

## Direction

The repository should increasingly contain **objects rather than promises**:

- working public utilities
- sanitized demos
- reproducible experiments
- test results
- architecture tied to implementation
- benchmarks
- case studies
- screenshots/diagrams when useful
- public-safe APIs or tools

Documentation remains important, but the long-term goal is for public proof to show what Nightcoder Designs actually builds.

---

## Additional Context

- Main GitHub Profile: https://github.com/brianjames829
- Website: https://nightcoderdesigns.com
- LinkedIn: https://www.linkedin.com/in/brianjames829
