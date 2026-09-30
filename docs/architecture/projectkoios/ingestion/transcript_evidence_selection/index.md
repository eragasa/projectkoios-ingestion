# `projectkoios.ingestion.transcript_evidence_selection`

**Status:** implemented bounded development vertical for downstream authoring.

This module selects exact `CleanTranscriptBlock.record_id` values from one
canonical [`CleanTranscript`](../../../../contracts/clean-transcript.md). It
returns canonically ordered page and block evidence with separate clean indexed
text and exact retained raw text. It does not make source-asset, reference,
rights, use, search, citation, generation, persistence, schema, API, workflow,
or private-data decisions.

## Public classes

- [`SelectedTranscriptBlockEvidence`](SelectedTranscriptBlockEvidence/index.md)
- [`SelectedTranscriptPageEvidence`](SelectedTranscriptPageEvidence/index.md)
- [`TranscriptEvidenceMappingBasis`](TranscriptEvidenceMappingBasis/index.md)
- [`TranscriptEvidenceSelectionLimitError`](TranscriptEvidenceSelectionLimitError/index.md)
- [`TranscriptEvidenceSelectionOutcome`](TranscriptEvidenceSelectionOutcome/index.md)
- [`TranscriptEvidenceSelectionRequest`](TranscriptEvidenceSelectionRequest/index.md)
- [`TranscriptEvidenceSelectionResult`](TranscriptEvidenceSelectionResult/index.md)
- [`TranscriptEvidenceSelector`](TranscriptEvidenceSelector/index.md)

## Contents

- [`schematic.md`](schematic.md) — action and evidence relationships.
- [`implementation.md`](implementation.md) — validation, ordering, warning,
  identity, and failure rules.
