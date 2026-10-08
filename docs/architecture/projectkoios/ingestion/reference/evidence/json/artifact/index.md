# `reference.evidence.json.artifact`

`ReferenceEvidenceArtifactJsonCodec` owns the exact `media_type`, `sha256`, and
`byte_length` JSON object used by extraction, transcript, and audit evidence.
It reconstructs `ReferenceEvidenceArtifact`, leaving digest and size invariants
to that domain record.
