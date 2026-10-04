# Native-text PDF corpus preparation

The corpus commands prepare and validate bounded native-text extraction work.
They reuse `PdfBatchPlan`, `koios-ingest-pdf-batch`, and the canonical PDF
extraction artifacts. They do not define a second extraction pipeline or a new
transcript format.

All filesystem roots are explicit. The caller chooses the source, plan, cache,
and output locations. These commands do not define the Project Koios deployment
layout and do not assume that the paths share a common parent.

## Prepare batch plans

Planning recursively discovers PDF files without following symbolic links,
reads each source with an exact byte-identity check, and orders paths by their
relative POSIX spelling. The planner enforces caller-configurable file-count,
per-file byte, and aggregate-byte limits within hard ceilings of 10,000 files,
512,000,000 bytes per file, and 10,000,000,000 aggregate bytes. Identical source
bytes are represented once. Each unique source receives a content-addressed source identity and output
directory.

```bash
koios-plan-pdf-corpus \
  --source-root SOURCE_DIRECTORY \
  --output PLAN_DIRECTORY \
  --max-files 10000 \
  --max-file-bytes 512000000 \
  --max-total-bytes 10000000000
```

The command is a dry run unless `--apply` is supplied. Apply publishes a private
`0700` directory containing existing `PdfBatchPlan` JSON files at mode `0600`.
Publication is create-once: an exact existing plan set is unchanged and a
race-safe exclusive rename makes a collision fail without replacement. `--batch-size` controls interruption
isolation and cannot exceed the existing 256-item batch-plan limit.

## Run owner extraction

Each generated file is consumed by the existing batch command:

```bash
koios-ingest-pdf-batch PLAN_FILE \
  --source-root SOURCE_DIRECTORY \
  --output-root EXTRACTION_DIRECTORY \
  --cache-root CACHE_DIRECTORY \
  --apply
```

The output contains the owner `extraction.json` and exact per-page native-text
artifacts. Newly created directories and files are private (`0700` and `0600`).
The planner does not run extraction, OCR, equation processing, a model, or an
indexer. Operators should use smaller batches when file-level restart boundaries
are required. Existing output is never silently replaced.

## Validate a completed extraction

```bash
koios-validate-pdf-corpus \
  --plans PLAN_DIRECTORY \
  --source-root SOURCE_DIRECTORY \
  --output-root EXTRACTION_DIRECTORY \
  --max-files 10000 \
  --max-source-bytes 512000000 \
  --max-total-bytes 10000000000
```

Validation is read-only. For every planned item it checks:

- source byte size and SHA-256 identity;
- confined, non-symlinked paths and private permissions;
- the exact output inventory with no missing or extra files;
- canonical owner extraction JSON and page artifacts;
- extraction configuration and source lineage; and
- strict semantic transcript replay through
  `read_pdf_extraction_transcript`.

The stdout summary reports document and page counts, pages with no native text,
low-native-text warnings, documents with at least one empty native-text page,
and total native-text bytes. It does not write a quality report into the corpus.

## Limits of the result

A successful validation establishes a consistent **native-text extraction
baseline**. It does not establish correct reading order, complete text,
proofreading quality, equation transcription, semantic correctness, retrieval
quality, or scientific validity. In particular, the result contains no OCR
outputs, equation-recognition outputs, embeddings, or search index unless a
separately authorized stage produced and validated them. It is not a completed
RAG corpus.

The repository already contains bounded owner capabilities for later stages,
including `TesseractOCRProcessor`, dry-run-first selective OCR batch
publication, deterministic OCR reconciliation, equation detection, assembly,
and recognition contracts, `Pix2TexCliEquationRecognizer`, equation
batch commands, structured and clean transcript composition, derivation audit,
and `OllamaMultimodalRegionProcessor`. Their existence is distinct from having
run them over a corpus.

Future corpus stages should remain separate and explicitly authorized:

1. select native-text-deficient pages from validated extraction evidence;
2. render and OCR only those bounded pages, then reconcile OCR with native text;
3. detect and, where required, transcribe equation regions;
4. compose and audit source-linked transcript artifacts; and
5. build embeddings or indexes only from an approved, validated transcript
   contract.

Those stages require their own immutable plans, resource identities,
publication rules, replay checks, and acceptance criteria. The repository now
provides those mechanics for selective local OCR, but selecting a plan and
executing it remain separately authorized operations outside the native-text
planner and validator.
