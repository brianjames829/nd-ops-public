# Repo Drift Scanner

> The archive remembers too much.

A small, deterministic Python experiment that scans a repository for statements that may have become stale after current truth changed.

It distinguishes between:

- **current drift** — stale statements in current/reference material that deserve review;
- **harmless ghosts** — stale statements preserved inside explicitly historical/archive material.

This is a public Nightcoder Designs experiment, not a commercial product name.

## Why

Documentation, architecture notes, READMEs, and plans accumulate old truth. A blind text search can find old words, but it cannot tell whether an old statement is a problem or legitimate history.

Repo Drift Scanner adds a tiny authority model so a statement in `README.md` can be treated differently from the same statement in `archive/2025-plan.md`.

No AI model is required.

## Requirements

- Python 3.10+
- no third-party packages

## Try the included haunted repository

From this directory:

```bash
python ghost_scan.py examples/demo_repo --config examples/truths.json
```

The demo declares PostgreSQL, API v3, and `Acme Relay` as current truth. Its README intentionally contains stale references, while an archive file contains old references that should remain untouched.

Expected shape of the result:

```text
THE ARCHIVE REMEMBERS TOO MUCH

CURRENT DRIFT        2
HARMLESS GHOSTS      2
HAUNTING SCORE       17  [Whispering]

README.md:5
  The application uses MongoDB for persistent data.
Verdict: CURRENT DRIFT — review recommended

archive/2025-plan.md:3
  At the time, the prototype used MongoDB and the working name was Project Rocket.
Verdict: HARMLESS GHOST — preserve history
```

The command exits with code `2` when current drift exists and `0` when no current drift is found, so it can later be used in scripts or CI.

## Open one door

Inspect a single file:

```bash
python ghost_scan.py examples/demo_repo --config examples/truths.json --door README.md
```

## Machine-readable mode

```bash
python ghost_scan.py examples/demo_repo --config examples/truths.json --json
```

## Configuration

`examples/truths.json` contains two things:

1. **authority rules** — path patterns mapped to classes such as `current`, `governing`, or `historical`;
2. **truth rules** — the current canonical statement plus stale phrases worth finding.

Example:

```json
{
  "id": "database",
  "description": "Current primary database",
  "canonical": "PostgreSQL",
  "stale_patterns": ["MongoDB"],
  "severity": 10
}
```

This v0.1 scanner does not infer truth. You declare the truth; it finds possible ghosts.

## Haunting score

Current drift contributes its configured severity. Historical ghosts contribute zero.

```text
0–10     Quiet
11–25    Whispering
26–50    Haunted
51–100   Poltergeist
100+     CALL THE ARCHITECT
```

The theatrical label is intentionally silly. The score underneath it is deterministic.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Deliberate limitations

v0.1 deliberately does not:

- use an LLM;
- rewrite files;
- decide canonical truth automatically;
- inspect Git history;
- understand semantic paraphrases;
- modify repositories;
- contact external services.

Those would be later experiments only if the deterministic scanner proves useful first.

## Public/private boundary

The included demo repository is fictional. Do not publish private configuration, private repository contents, credentials, or sensitive internal truth rules merely to use this tool publicly.
