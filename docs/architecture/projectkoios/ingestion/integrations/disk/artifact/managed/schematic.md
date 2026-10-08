# `projectkoios.ingestion.integrations.disk.artifact.managed` schematic

```text
artifact_id
    |
    v
explicit binding inventory -> canonical relative path
    |
    v
authority check + descriptor-relative no-follow open
    |
    v
regular-file and byte-bound checks
    |
    v
transient chunks -> neutral verifier
```
