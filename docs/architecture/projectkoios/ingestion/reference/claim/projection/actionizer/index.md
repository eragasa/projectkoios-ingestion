# `reference.claim.projection.actionizer`

`actionizer.py` owns `ReferenceClaimCandidateProjectionActionizer`. It requires
reusable evidence, a positive locator match, and exact evidence/transcript
lineage, then returns one immutable `ReferenceClaimCandidate`. It has no retry,
approval, publication, or acceptance behavior.
