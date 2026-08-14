# Tesser v0.2 Repository Ingestion Spine — Engineering Case Study

Updated: 2026-08-14

Status: **Public-safe engineering proof**

This artifact documents the design and validation state of the first real ingestion implementation inside Nightcoder Designs' private Tesser intelligence architecture.

It intentionally explains the engineering problem, constraints, structure, and lessons without publishing private repository contents, internal memory, credentials, or the private runtime itself.

---

## Problem

Nightcoder Designs maintains different kinds of version-controlled information across multiple repositories.

Those sources are not interchangeable.

A current governing rule should not be treated as equivalent to:

- an old research note,
- a historical decision,
- a creative exploration,
- a continuity memory,
- or a public proof artifact.

At the same time, future AI/model layers should not need to own the source memory themselves.

The first technical problem was therefore smaller than "build an AI system":

> Build a reliable, model-independent way to ingest explicitly approved source repositories while preserving enough provenance and authority context for later retrieval and reasoning.

---

## Core Constraints

The v0.2 design was intentionally constrained.

### Source control remains authoritative

The ingestion output is derived state. Version-controlled source repositories remain canonical.

### Models are downstream

No embedding provider, LLM, agent framework, or model API is required for ingestion.

### Approval is explicit

A repository must be present in the approved-source registry before the ingestion CLI will process it.

Approval grants read/index scope only. It does not imply write authority.

### Provenance must survive ingestion

A later retrieval or reasoning layer should be able to determine where a document came from and which source version produced it.

### Partial ingestion should fail visibly

For GitHub ingestion, the adapter refuses to silently accept a truncated repository tree.

---

## High-Level Flow

```text
approved repository registry
        ↓
read-only source adapter
        ↓
file filtering + normalization
        ↓
authority / privacy classification
        ↓
content hashing + provenance
        ↓
deterministic chunking
        ↓
documents.jsonl + manifest.json
        ↓
future structured storage / retrieval
```

The ingestion layer does not perform AI reasoning.

Its job is to produce stable, inspectable source records that later systems can reason over.

---

## Implemented Structure

### Shared source contracts

The implementation uses shared data structures for repository policy, source documents, and document chunks so local and GitHub-backed ingestion produce the same general record shape.

A source document preserves public-safe categories such as:

- repository
- path
- branch
- source kind
- authority class
- privacy class
- content type
- content hash
- commit/blob provenance when available
- ingestion timestamp
- deterministic chunk identifiers

### Two source adapters

**Local repository adapter**

Reads approved local Git clones, captures the current Git commit when available, filters supported files, normalizes text, hashes content, classifies it, and creates chunks.

**GitHub repository adapter**

Reads approved repositories through the GitHub REST API using read access, captures commit/blob provenance, validates the returned tree, decodes supported text files, and emits the same source-document model.

### Deterministic normalization and chunking

Text normalization and chunk generation are deterministic.

The same source text and document identity should produce stable chunk identifiers and boundaries rather than allowing a model provider to define the source representation implicitly.

### Authority classification

The prototype introduces simple deterministic authority/context classes so downstream retrieval can distinguish different source roles.

Examples include:

- governing
- current
- canonical
- structured state
- operational
- continuity
- historical
- research
- creative
- public proof
- lower-priority reference material

These classes are **not truth scores**. They are context signals for later retrieval and conflict handling.

### CLI output

The ingestion CLI emits:

```text
runtime/ingestion/
  documents.jsonl
  manifest.json
```

The manifest summarizes document/chunk counts and source classifications.

Derived runtime output is not treated as canonical source material.

---

## Validation State

The initial implementation was locally validated with:

- **7 unit tests passing**
- **CLI smoke test passing**
- deterministic chunk-ID checks
- approved-source registry checks
- duplicate-registry rejection
- authority-classification checks
- local file filtering/provenance checks
- successful serialization of ingestion records

### Important current limitation

The complete end-to-end run across the real approved Nightcoder Designs repository set has **not yet been validated**.

This artifact therefore does **not** claim a production-ready ingestion runtime, production manifest, or completed knowledge system.

The next engineering gate is real-repository ingestion validation before promoting the architecture into a structured knowledge/runtime layer.

---

## Deliberate Non-Goals for v0.2

The implementation intentionally does not yet add:

- PostgreSQL
- vector databases / embeddings
- semantic retrieval
- model APIs
- agent orchestration
- autonomous writes
- web UI
- wallet access
- financial authority
- live webhook/event infrastructure

The purpose of v0.2 is to prove the source-ingestion boundary before adding more powerful layers.

---

## Why This Architecture Matters

A model-independent intelligence system cannot be meaningfully independent if its memory only exists inside model context or provider-specific conversation history.

The ingestion spine creates the first bridge between controlled source memory and future reasoning systems while preserving:

- provenance
- authority context
- privacy classification
- reproducibility
- source ownership
- model replaceability

It also makes later failures easier to reason about because the source layer remains inspectable without requiring an AI model to explain itself.

---

## Reusable Lessons

### Separate memory from cognition

Durable source memory and AI reasoning do not need to be the same system.

### Preserve authority semantics early

Ingesting everything as equally authoritative text creates retrieval problems later.

### Keep the first layer boring

Hashing, explicit allowlists, deterministic records, tests, and provenance are less exciting than autonomous agents. They are also the machinery those agents eventually need if they are expected to behave coherently.

### Refuse silent partial state

A system should fail visibly when it cannot establish that the source set is complete enough for the operation it claims to perform.

### Do not promote architecture ahead of validation

A clean design and passing unit tests are evidence of an implementation milestone, not evidence that the full system already works in production.

---

## Private / Public Boundary

This case study intentionally omits:

- private repository contents
- private memory/strategy records
- credentials or authentication material
- internal prompts
- private data examples
- exact private source registry contents where unnecessary
- future restricted runtime details

Tesser is private Nightcoder Designs intelligence infrastructure.

This public artifact documents an engineering lesson from that work. It does not expose or package the private intelligence system as a public product.

---

## Current Status

**Implemented:** v0.2 ingestion spine  
**Locally tested:** yes  
**Real full-source validation:** pending  
**Production-ready:** no  
**Next gate:** validate against the actual approved repository set, then design structured storage/retrieval from observed results

