# `projectkoios.ingestion.integrations.disk.artifact` implementation

This adapter hierarchy owns physical disk resolution and byte access for externally managed artifacts. Backend-neutral reference and verification semantics remain under `artifact.managed`; current disk behavior is defined by the `managed` child package.
