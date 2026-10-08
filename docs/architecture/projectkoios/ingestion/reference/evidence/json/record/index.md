# `reference.evidence.json.record`

`ReferenceEvidenceRecordJsonCodec` owns the exact closed root object, including
contract metadata, completeness, child-object positions, limitations, and
aggregate reconstruction. It delegates each nested object to its defining JSON
codec and uses `ReferenceEvidenceJsonValueReader` for root scalar fields. It
does not parse bytes, select formatting, or translate parser errors.
