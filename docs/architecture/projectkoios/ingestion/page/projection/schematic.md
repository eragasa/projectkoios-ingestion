# `projectkoios.ingestion.page.projection` schematic

```text
ReadingEvidenceSourceResult
  document
  projection_result_id
  inventory.inventory_id
             +
ManagedArtifactVerificationResult
  exact fresh document.managed_artifacts coverage
             |
             v
PageProjectionRequest
  mandatory paragraph + heading policy
  include_figure_captions: bool
             |
             v
PageProjectionActionizer (pure)
             |
             v
PageProjectionResult
  complete citation-aligned page inventory
  paragraph + heading text
  optional unique figure-caption text
  upstream reading limitations
  mandatory non-authority limitations
             |
      +------+------+
      |             |
      v             v
Search-owned     Ingestion enrichment
chunking         exact raw text/span/warning facts
                 explicit caption unavailability
      |             |
      +------+------+
             |
             v
Downstream owner composition by exact source_evidence_id
```

Only the typed current-schema inputs shown above are accepted. The action performs no I/O and emits no table, equation, media, or payload text.
