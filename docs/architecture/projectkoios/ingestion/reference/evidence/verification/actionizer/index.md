# `reference.evidence.verification.actionizer`

## Owner

`ReferenceEvidenceVerificationActionizer` is a stateless
`DataObjectActionizer[ReferenceEvidenceVerificationRequest, ReferenceEvidenceVerificationResult]`.
Its only operation is `action(*, request=...)`.

The action requires reusable evidence, compares the record with the expected
source digest/size/media identity, verifies each supplied artifact through its
recorded `ReferenceEvidenceArtifact`, and returns typed coverage. Mismatch
raises `ReferenceEvidenceVerificationError`. It performs no I/O, path
construction, independent audit, semantic judgment, or lifecycle inference.
