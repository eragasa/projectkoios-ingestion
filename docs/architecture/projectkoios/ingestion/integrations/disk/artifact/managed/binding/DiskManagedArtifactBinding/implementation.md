# `DiskManagedArtifactBinding` implementation

The frozen binding requires a canonical `managed-artifact:sha256:` identity and a bounded UTF-8 `PurePosixPath` string. Absolute paths, traversal components, dot components, normalization changes, NULs, and backslashes are rejected before provider access.
