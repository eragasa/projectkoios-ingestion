# `reference.evidence.json.audit`

`ReferenceEvidenceAuditJsonCodec` owns the exact audit artifact, contract,
report/status/scope, revalidation flag, producer, audited identities, ordered
layer-count array, and finding-count wire object. Individual layer-count object
mapping belongs to `json/layer.py`; domain ordering and uniqueness belong to the
semantic inventory in `layer.py`.
