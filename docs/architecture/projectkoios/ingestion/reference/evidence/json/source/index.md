# `reference.evidence.json.source`

`ReferenceEvidenceSourceJsonCodec` owns the exact source blob, hash algorithm,
content digest, byte length, and media type wire object. It contains no locator,
filename, protected content, or backend details and delegates semantic source
identity invariants to `ReferenceEvidenceSource`.
