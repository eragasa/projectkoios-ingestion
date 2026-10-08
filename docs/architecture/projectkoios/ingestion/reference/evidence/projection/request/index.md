# `reference.evidence.projection.request`

## Owner

`ReferenceEvidenceProjectionRequest` is one frozen `DataObjectActionRequest`
containing an `ExtractionResult`, extraction artifact bytes, `CleanTranscript`,
clean-transcript result bytes, `DerivationAuditReport`, and derivation-audit
artifact bytes.

Construction validates exact input types and bounds each byte payload before
the action begins. It adds no request identity, configuration, metadata bag,
authority, or Workflow state because none is required by this pure operation.
Cross-input lineage and producer-byte consistency are action behavior.
