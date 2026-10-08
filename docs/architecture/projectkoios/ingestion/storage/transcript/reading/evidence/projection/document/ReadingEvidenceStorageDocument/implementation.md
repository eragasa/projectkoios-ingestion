# `ReadingEvidenceStorageDocument` implementation

Creation validates scope and semantic identity, serializes the payload through strict canonical JSON, computes the pre-marker content digest, inserts that marker, then computes the full canonical digest and member identity. Construction reparses and recomputes all evidence; stored digests are never trusted.
