# `ManagedArtifactByteProvider` implementation

The abstract port exposes a provider implementation identity and `open_chunks`. Calls receive one exact reference, authority identity, maximum byte count, and maximum chunk size. Implementations return a context-managed ordered byte iterator so resources are released even when verification stops early. They raise `ManagedArtifactVerificationError` rather than returning locators, handles, or provider-native exceptions.
