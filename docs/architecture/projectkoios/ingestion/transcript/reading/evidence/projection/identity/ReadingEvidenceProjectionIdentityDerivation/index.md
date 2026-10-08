# `ReadingEvidenceProjectionIdentityDerivation`

Owner of bounded request, document, inventory, and result identity material. It validates before hashing, serializes each typed identity input exactly once through the repository canonical one-way serializer, and fingerprints those exact bytes through `SHA256Fingerprinter`; it is not a `JsonContract`.
