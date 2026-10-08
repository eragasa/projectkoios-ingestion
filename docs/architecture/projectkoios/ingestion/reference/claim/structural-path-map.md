# Reference claim-candidate structural path map

| Old path | New owner |
| --- | --- |
| `reference_claim_candidate.py` contract constants | `reference/claim/definition.py` |
| `reference_claim_candidate.py` candidate record | `reference/claim/candidate.py` |
| `reference_claim_candidate.py` errors | `reference/claim/error.py` |
| `reference_claim_candidate.py` status | `reference/claim/status.py` |
| `reference_claim_candidate.py` claim identity and candidate identity derivation | `reference/claim/identity.py` |
| fixed candidate limitations | `reference/claim/limitation.py` |
| `ReferenceClaimCandidate.create()` input | `reference/claim/projection/request.py` |
| `ReferenceClaimCandidate.create()` operation | `reference/claim/projection/actionizer.py` |
| `tests/test__ReferenceClaimCandidate.py` | `tests/projectkoios/ingestion/reference/claim/test__ReferenceClaimCandidateProjection.py` |

`src/python/projectkoios/ingestion/reference_claim_candidate.py` is deleted.
There is no compatibility module, package re-export, legacy constructor, or
root `projectkoios.ingestion` export.

Page-location ownership is migrated by the separately documented
[`reference/page/location`](../page/location/structural-path-map.md) slice.
`clean_transcript.py` remains unchanged under the
constraints in
[`clean-transcript-module-size.md`](../../../../../tasks/tech_debt/clean-transcript-module-size.md).
