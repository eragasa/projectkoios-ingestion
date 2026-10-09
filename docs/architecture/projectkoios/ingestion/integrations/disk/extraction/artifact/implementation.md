# Disk extraction-artifact implementation

This adapter maps opaque extraction-artifact references to unique canonical root-relative paths. It performs descriptor-relative `O_NOFOLLOW` traversal, rejects nonregular files and symlinks, enforces exact authority and byte bounds, and translates provider failures to `ExtractionArtifactReaderError`.

It reads only current extraction artifacts through the backend-neutral `ExtractionArtifactReader` port. It does not infer paths, decode legacy contracts, publish journals, contact MongoDB, or own migration iteration.
