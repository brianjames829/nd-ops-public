# Repo Drift Scanner v0.4 Candidate

Status: **candidate / not yet released**

## Why this exists

A real Nightcoder Designs repository scan exposed a useful distinction that v0.3.2 could not represent cleanly:

```text
stale-looking statement
+
current source explicitly says the conflict is known and unresolved
=
not a clean suppression
not harmless history
not necessarily blocking drift
```

The prior scanner could only choose among current drift, historical ghost, suppression, or an expired-suppression review.

v0.4 promotes **REVIEW** into a first-class deterministic disposition.

## New concept: acknowledgements

A rule-specific acknowledgement says:

> This match is real and should remain visible, but the repository explicitly knows it is unresolved or intentionally retained for review.

Example:

```json
{
  "truths": [
    {
      "id": "system-origin",
      "description": "Current system origin",
      "canonical": "Current origin model",
      "stale_patterns": ["older origin statement"],
      "severity": 15
    }
  ],
  "acknowledgements": [
    {
      "path": "STATE.md",
      "rule_id": "system-origin",
      "reason": "Older canon intentionally retained pending reconciliation",
      "expires": "2026-12-31"
    }
  ]
}
```

The finding remains in normal reports as:

```text
REVIEW
```

It does not add to the haunting score and does not fail the scan by default.

## Inline review marker

Rule-specific inline review is also supported:

```markdown
<!-- drift-review: system-origin -->
Older origin statement remains here pending reconciliation.
```

As with `drift-ignore`, the marker may be on the same line or the immediately preceding line.

## Suppression still means something different

```text
SUPPRESS
known match is intentionally hidden from normal reports

ACKNOWLEDGE / REVIEW
known match stays visible and requires human/system judgment
```

If both an active suppression and an acknowledgement match the same rule/path, suppression remains sufficient.

Historical/archive authority still wins conceptually: an archived statement remains a harmless ghost rather than being promoted into a current review merely because an acknowledgement also matches it.

## Strict review mode

Default behavior remains non-blocking for reviews.

For CI or stricter repository gates:

```bash
python ghost_scan.py . --config rules.json --fail-on-review
```

With `--fail-on-review`, any text or contract REVIEW signal causes exit code `2`.

## Expiration

Acknowledgements may use `expires` just like suppressions.

Expired dispositions remain visible as REVIEW signals with the expiration date included in the reason. Teams that want expiry to become blocking can combine expiration with `--fail-on-review` in CI.

## Reporting

Text and Markdown reports now describe text REVIEW findings generically instead of assuming every review came from an expired suppression.

JSON keeps the existing suppression fields for backward compatibility and additionally exposes:

```json
"disposition_source"
"disposition_reason"
```

for text-review findings.

## Candidate validation performed

A focused local harness covered:

- acknowledgement config parsing,
- acknowledgement-to-review conversion,
- rule-specific inline `drift-review`,
- suppression precedence,
- historical archive behavior,
- expired acknowledgement visibility,
- text/Markdown/JSON disposition reporting,
- default non-blocking review behavior,
- `--fail-on-review` exit behavior,
- v0.4 version reporting.

The branch also adds repository unittest coverage in `tests/test_v04_reviews.py`.

## What this is not

This is **not semantic AI**.

The scanner still does not decide whether two arbitrary paragraphs philosophically agree. The repository must explicitly declare the rule and the acknowledgement.

That is intentional.

A future Tesser layer may propose or explain acknowledgements using richer context, but deterministic Repo Drift Scanner should remain the inspectable enforcement engine underneath.
