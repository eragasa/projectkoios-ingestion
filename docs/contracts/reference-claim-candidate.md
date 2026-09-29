# Reference claim candidate

## Contract metadata

| Field | Value |
|---|---|
| Contract ID | `projectkoios.ingestion.reference-claim-candidate` |
| Target version | `0.1.0` |
| Status | Proposed |
| Owner | `projectkoios-ingestion` |
| Acceptance authority | Project Koios operator after ingestion and workflow-consumer review |
| Dependencies | `projectkoios.ingestion.reference-evidence@0.1.0`, `projectkoios.ingestion.reference-page-locator@0.1.0` |
| Consumer | `projectkoios.workflow.reference_review` candidate adapter |
| Effective baseline | None while proposed |

## Scope

A reference claim candidate binds one externally owned research-claim identity
to one positive page-locator result and its complete reusable reference-evidence
lineage. Ingestion does not author, normalize, interpret, accept, reject, or
publish the claim.

Creation requires:

- a complete reusable `ReferenceEvidenceRecord`;
- a `ReferencePageLocatorResult` with `status=match`;
- exact record and transcript identities across both inputs; and
- a content identity with grammar `research-claim:sha256:<digest>` supplied by
  the claim-owning research system.

A no-match locator cannot produce a candidate.

## Payload and identity

The candidate contains only content-derived identities, source digest identity,
page index, page-text digest and byte length, matched topic-anchor identities,
status, limitations, and contract metadata. It contains no claim text,
quotation, page text, source path, credentials, authority, reviewer identity,
decision, or publication state.

Every field participates in the candidate identity. Constructors reject unknown
identity grammars, source-blob/hash mismatch, unbounded page length, empty or
noncanonical anchor sets, status changes, incomplete limitations, and identity
tampering.

## Authority limits

`manual_review_required` is the only candidate status. It means only that
mechanical page-location evidence exists for later review. It is not claim
support, citation acceptance, extraction accuracy, scientific validation,
rights clearance, retention approval, or publication approval.

Workflow may consume the candidate as typed non-authorizing input. A retained
or excluded review disposition requires a separate human decision record and
separate workflow authority. Publication remains outside this contract.
