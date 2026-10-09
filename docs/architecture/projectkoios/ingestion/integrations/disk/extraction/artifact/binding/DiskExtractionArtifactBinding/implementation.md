# `DiskExtractionArtifactBinding` implementation

The immutable binding validates bounded UTF-8 reference text and a portable canonical relative path. Absolute paths, traversal components, empty components, backslashes, and NUL bytes are rejected before provider access.
