# Monitoring & Edge Security Alignment Case

Last Updated: 2026-02-24

Purpose:
Document a real-world interaction between edge security controls and uptime monitoring, and the resolution implemented to align reliability and protection.

---

## Environment

- WordPress + WooCommerce (shared hosting)
- Cloudflare (DNS, TLS, edge security)
- BetterStack (external uptime monitoring)

---

## Summary

External uptime monitoring reported HTTP 403 responses from non-US probe regions.

End-user access from primary geography (US) remained unaffected.

Issue identified as an interaction between Cloudflare edge security rules and globally distributed monitoring probes.

No customer-visible outage occurred.

---

## Detection

- Alert source: BetterStack uptime monitor
- Symptom: HTTP 403 responses from Europe, Asia, and Australia probe regions
- Manual verification: Site accessible via browser (HTTP 200)

Classification:
Monitoring / security-control interaction  
Not a true service outage

---

## Root Cause

A Cloudflare security rule applied a **Managed Challenge** to traffic originating outside the United States:

Global BetterStack probes received challenge responses.

Monitoring interpreted the challenge response as degraded availability.

---

## Risk

- False-positive availability alerts
- Alert fatigue
- Reduced trust in monitoring signals
- Potential future masking of real outages

---

## Decision

Rather than weaken edge security globally:

1. Removed the blanket geo-based challenge rule.
2. Replaced it with endpoint-specific protections:
   - Managed Challenge on `/wp-login.php`
   - Block on `/xmlrpc.php`
   - Login rate limiting (5 req/min → 10 minute block)
   - Bot Fight Mode enabled
3. Verified monitoring probe behavior post-change.

Security posture was strengthened while restoring monitoring accuracy.

---

## Result

- Monitoring probes now return HTTP 200 consistently.
- No further false-positive alerts observed.
- Edge protection remains active and targeted.
- Monitoring and security posture aligned.

---

## Preventative Controls

- Avoid broad geo-based challenge rules without validating monitoring impact.
- Prefer endpoint-scoped protection over global traffic rules.
- Validate monitoring behavior after any edge security change.
- Close documentation loop immediately after resolution.

---

## Lessons

Security and observability must be designed together.

Monitoring should reflect real user experience, not bot-mitigation artifacts.

Targeted controls reduce noise while preserving protection.

---

## Status

Closed.
Monitoring and edge security configuration aligned as of 2026-02-24.
