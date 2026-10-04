# Private reference multimodal workflow

These numbered scripts preserve the operational workflow used to prepare and
validate the private nine-document reference corpus. They are checked in so the
workflow does not depend on `/private/tmp` surviving.

The scripts are operational records, not package modules or public CLIs. They
contain machine-local absolute paths under `/Users/eugene/projects/projectkoios`
and must be invoked from this repository with its virtual environment:

```bash
.venv/bin/python workflows/NNN.description.py
```

Do not run the sequence blindly. Every script uses retained artifacts and
create-once or exact-byte checks, but some stages have additional authorization
boundaries. In particular, `011` and `015` invoke the external Pix2Tex model.
Their bounded canaries have already completed and **must not be rerun or
expanded without new operator authorization**. The configured Pix2Tex path is
closed as unsuitable for unattended corpus execution.

## Approximate order

| Step | Script | Purpose |
|---:|---|---|
| 001 | `001.enrich_kittel8ed_multimodal.py` | Legacy `doc-01` detection, structured composition, and equation/figure evidence workflow. Retained for audit; do not resume model execution. |
| 002 | `002.build_kittel8ed_reading_transcript.py` | Build the legacy `doc-01` reading projection. |
| 003 | `003.process_selected_reference_multimodal.py` | Legacy `doc-02`–`doc-06` detection, equation handling, and reading projection runner. Retained for replay/audit; do not use it to resume the closed Pix2Tex queue. |
| 004 | `004.validate_selected_reference_multimodal.py` | Validate legacy `doc-01`–`doc-06` reading projections against source and composed page text. |
| 005 | `005.prepare_pending_reference_multimodal.py` | Freeze deterministic plans for `doc-07`–`doc-09`. |
| 006 | `006.render_pending_reference_multimodal_candidates.py` | Retain deterministic equation, figure, and table evidence. |
| 007 | `007.build_pending_reference_candidate_quality.py` | Build bounded quality inventories and equation assemblies. |
| 008 | `008.build_pending_reference_execution_plan.py` | Build the frozen equation execution plan. |
| 009 | `009.validate_pending_reference_multimodal_preparation.py` | Validate preparation identities, hashes, coverage, and permissions. |
| 010 | `010.finalize_reference_multimodal_preparation_supersession.py` | Mark the nondeterministic preparation root audit-only. |
| 011 | `011.run_pending_reference_pix2tex_canary.py` | **Model execution:** original bounded 30-item canary. Closed; do not rerun without authorization. |
| 012 | `012.audit_pending_reference_pix2tex_canary.py` | Audit original canary region and output quality. |
| 013 | `013.validate_pending_reference_pix2tex_canary.py` | Validate original canary artifacts. |
| 014 | `014.build_pending_reference_equation_eligibility.py` | Build the 1,906-item deterministic eligibility inventory. |
| 015 | `015.run_pending_reference_pix2tex_canary_v2.py` | **Model execution:** matched bounded 30-item canary. Closed; do not rerun without authorization. |
| 016 | `016.audit_pending_reference_pix2tex_canary_v2.py` | Audit matched canary region and output quality. |
| 017 | `017.validate_pending_reference_pix2tex_canary_v2.py` | Validate matched canary artifacts. |
| 018 | `018.audit_pending_reference_pix2tex_output_quality.py` | Replay retained canary results and measure deterministic warning coverage. |
| 019 | `019.build_pending_reference_reading_transcripts.py` | Publish the equation deferral inventory and deterministic `doc-07`–`doc-09` reading transcripts without recognized equation text. |
| 020 | `020.validate_pending_reference_reading_transcripts.py` | Validate transcript identities, evidence hashes, review gates, coverage, and permissions. |
| 021 | `021.recompose_neaman_equation_evidence.py` | Correct `doc-06` by retaining every primary equation-region reference independently of historical recognition output and resolve its stale mutable progress state. |
| 022 | `022.build_reference_reading_corpus_coverage.py` | Audit all nine reading transcripts and freeze the pre-correction coverage gap found in legacy `doc-01`–`doc-05`. |
| 023 | `023.recompose_legacy_reference_equation_evidence.py` | Correct `doc-01`–`doc-05`, retain every selected equation-region reference, and discard historical recognized equation text. |
| 024 | `024.build_reference_reading_corpus_coverage_v2.py` | Validate and reconcile the authoritative nine-document reading corpus after legacy recomposition. |
| 025 | `025.validate_reference_reading_corpus_coverage.py` | Recheck all nine transcripts, equation review gates, evidence hashes, unique identities, media, totals, and private permissions. |
| 026 | `026.select_recognition_independent_equation_evidence.py` | Classify every prepared equation assembly from detector and assembly evidence only, retaining all candidate media without reading recognition output. |
| 027 | `027.build_recognition_independent_reading_transcripts.py` | Compose and validate the three-book reading collection directly from workflow 026, proving semantic equivalence to the prior collection without reading recognition output. |
| 028 | `028.build_recognition_independent_corpus_coverage.py` | Rebuild and validate nine-document coverage with workflow 027, then supersede the prior three-book and corpus roots after semantic equivalence passes. |

Later steps may read artifacts produced by earlier steps. Preserve exact source
PDF bytes and existing artifact roots. Do not use these scripts to mutate source
references, publish replacement text, connect to live databases, perform Search
indexing, or transmit private evidence externally.

## Workflow modules

`equation_evidence_selection.py` owns the path-free, recognition-independent
classification used by workflow 026. `reading_transcript_equation_evidence.py`
owns projection of one selected assembly into an equation record, while
`reading_transcript_figure_evidence.py` and
`reading_transcript_table_evidence.py` own figure and page-specific table
projection. `reading_transcript_page.py` owns text-source separation, visual
ordering, and page identity for workflow 027. These modules remain here until
the working workflow boundaries are stable enough to promote into `src/`.
