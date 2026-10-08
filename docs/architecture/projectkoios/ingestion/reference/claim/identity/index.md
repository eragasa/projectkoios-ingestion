# `reference.claim.identity`

`identity.py` owns `ResearchClaimIdentity` and
`ReferenceClaimCandidateIdentityDerivation`. The first is a syntax-only typed
reference to an external claim; it does not assert existence or acceptance. The
second validates all ordered candidate identity inputs before reproducing the
historical stable identifier.
