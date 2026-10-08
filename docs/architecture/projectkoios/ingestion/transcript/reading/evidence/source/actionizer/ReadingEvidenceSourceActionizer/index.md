# `ReadingEvidenceSourceActionizer`

Abstract backend-neutral synchronous action `ReadingEvidenceSourceRequest -> ReadingEvidenceSourceResult`. Concrete providers return domain records only and cannot leak BSON, cursors, clients, paths, raw JSON, or storage configuration.
