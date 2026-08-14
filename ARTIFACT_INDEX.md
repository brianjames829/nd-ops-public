# Artifact Index

Updated: 2026-08-14

Purpose:
Index public Nightcoder Designs proof artifacts, what each artifact demonstrates, and current publication status.

This file helps readers understand the purpose of the repository without guessing from filenames.

---

## Published Artifacts

| Artifact | Demonstrates | Status |
|---|---|---|
| `tools/repo-drift-scanner/` | Runnable Python utility for stale-truth detection plus deterministic repository contracts, source authority, structured state, lifecycle, current surfaces, output ownership, append-only history, review signals, source-coverage accounting, machine-readable output, and tests | Published / runnable — v0.3.1 |
| `TESSER_INGESTION_SPINE_CASE.md` | Model-independent repository ingestion, provenance, source authority, deterministic chunking, testing boundaries, and explicit non-goals | Published |
| `MONITORING_EDGE_ALIGNMENT_CASE.md` | Monitoring/security interaction, false-positive analysis, corrective action, and reliability discipline | Published |
| `ARCHITECTURE_OVERVIEW.md` | High-level production environment architecture, trust boundaries, and intentional omissions | Published |
| `PRODUCT_SERVICE_PROOF_NOTE.md` | Evolution from internal documentation discipline into first product/service proof path | Published |
| `PUBLICATION_POLICY.md` | Public/private artifact boundary and sanitization expectations | Published |

---

## Artifact Categories

### Runnable Utilities

Small public tools that can be cloned, run, inspected, and tested without access to private Nightcoder Designs systems.

Current artifacts:
- `tools/repo-drift-scanner/` — Repo Drift Scanner v0.3.1, a deterministic stale-truth and repository-contract validator with source-coverage visibility and fictional examples

### AI / Data / Knowledge-System Proof

Artifacts showing implemented work around model-independent intelligence infrastructure, source ingestion, provenance, structured knowledge, retrieval, and related system boundaries.

Current artifacts:
- `TESSER_INGESTION_SPINE_CASE.md`
- `tools/repo-drift-scanner/` — a public deterministic experiment applying source-authority and continuity-contract ideas without using an AI model

### Reliability / Monitoring Proof

Artifacts showing failure-mode thinking, monitoring behavior, and corrective action.

Current artifacts:
- `MONITORING_EDGE_ALIGNMENT_CASE.md`

### Architecture Proof

Artifacts showing how systems are structured at a safe public level.

Current artifacts:
- `ARCHITECTURE_OVERVIEW.md`
- `TESSER_INGESTION_SPINE_CASE.md`

### Product / Service Execution Proof

Artifacts showing how operational discipline becomes product/service infrastructure.

Current artifacts:
- `PRODUCT_SERVICE_PROOF_NOTE.md`

### Publishing Boundary Proof

Artifacts showing how public proof is reviewed and sanitized.

Current artifacts:
- `PUBLICATION_POLICY.md`

---

## Future Artifact Types

As real work becomes mature enough to publish safely, this repository may include:

- additional small working public utilities
- sanitized automation / agent case studies
- Base / Ethereum / Web3 technical experiments
- API and developer-tool proof
- test/benchmark artifacts
- public-safe data/provenance examples
- architecture tied directly to implemented systems
- additional reliability and incident case studies
- screenshots or diagrams where they materially improve understanding
- public-safe product/build release notes

Future artifacts must follow `PUBLICATION_POLICY.md` before release.

---

## Publication Rule

The repository should show **real work, not roadmap theater**.

A planned system is not proof.
A design is not a production claim.
A passing unit test is not an end-to-end validation.
A private implementation should only become public evidence through intentional sanitization.

Finished work beats performative documentation.

---

Owner:
Brian James

Created:
2026-05-25
