# Reference claim-candidate implementation

## Problem

`reference_claim_candidate.py` flattens reference, claim, candidate-record,
validation, failure, status, and projection ownership into one root module. Its
`ReferenceClaimCandidate.create()` method also performs a synchronous
cross-record operation without an immutable request or Ingestion Base
actionizer.

## Design

The clean hierarchy is `projectkoios.ingestion.reference.claim`. Package
initializers remain docstring-only and consumers import defining leaves.

Projection is the synchronous boundary:

```text
ReferenceClaimCandidateProjectionRequest
    -> ReferenceClaimCandidateProjectionActionizer
    -> ReferenceClaimCandidate
```

The request binds one reusable `ReferenceEvidenceRecord`, one positive
`ReferencePageLocatorResult`, and one bounded research-claim identity. The
actionizer checks evidence reuse, positive-match status, and exact locator
lineage before constructing the immutable candidate result.

The candidate remains payload-free and content-addressed. It reuses the typed
page-location anchor-identity inventory, owns closed semantic limitations, and
uses a bounded immutable identity derivation rather than raw string tuples or a
static helper. `ResearchClaimIdentity` owns the exact external claim-ID grammar;
there is no generic validator namespace or family of procedural `require_*`
helpers. Stable identity bytes, contract constants, field order, and
non-acceptance meaning remain unchanged. No compatibility module or root-package
re-export is retained.

## Bounds and authority

Existing locator page and anchor bounds remain authoritative for candidate
fields copied from a locator result. Validation occurs before stable identity
construction. The candidate status remains `manual_review_required`; projection
does not infer support, acceptance, publication suitability, or scientific
validity.

## Validation

Required evidence includes focused action tests, stable-ID replay, hierarchy
and action-contract smell gates, Ruff, mypy, the complete test suite, build,
and clean-wheel proof that the old module and root exports are absent.
