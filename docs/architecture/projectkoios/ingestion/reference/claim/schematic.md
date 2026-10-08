# Reference claim-candidate schematic

```text
ReferenceEvidenceRecord ─┐
                         ├─> ProjectionRequest ─> ProjectionActionizer
PageLocatorResult ────────┤                              │
Research claim identity ──┘                              v
                                               ReferenceClaimCandidate
                                               manual_review_required
```

The result contains identities and bounded counts only; source, page, claim,
and quotation payloads remain absent.
