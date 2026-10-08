# `reference.evidence.projection.actionizer`

## Owner

`ReferenceEvidenceProjectionActionizer` is a stateless
`DataObjectActionizer[ReferenceEvidenceProjectionRequest, ReferenceEvidenceRecord]`.
Its only operation is `action(*, request=...)`.

The action verifies canonical producer artifacts, completed extraction,
automated-unreviewed transcript status, source/document agreement, passing
zero-finding audit status, and layer-count shape before constructing the exact
child records and aggregate result. It has no forwarding build method, hidden
configuration, I/O, retries, acceptance, or publication behavior.
