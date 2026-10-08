# `reference.page.location.verification`

`verification.py` owns `ReferencePageEvidenceVerifier`, which binds one exact
reusable-evidence record and clean transcript as immutable instance state and
selects one verified page. It is not a static helper namespace. Invalid lineage
fails before anchor matching.
