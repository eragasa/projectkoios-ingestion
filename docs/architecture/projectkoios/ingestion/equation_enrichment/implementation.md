# `ingestion.equation_enrichment` implementation

The module depends on the nominal `PageRegionRenderer` base and has no concrete
PDF-adapter default. `DeterministicEquationAssembler` requires an injected
renderer. Assembly grouping, sanitization, bounds, and evidence identities
remain deterministic.

Pix2Tex recognizer behavior version 3 is an external effect worker. The
repository workflow creates one immutable, vendor-neutral
`EquationRecognitionRequest` token for an exact assembly artifact and processor
identity; the worker emits an immutable `EquationRecognitionArtifact` result
token. The concrete
`integrations.pix2tex.recognizer.Pix2TexCliEquationRecognizer` implements the
`AbstractEquationRecognizer` action boundary. SNAKES remains outside the
ingestion package in the separate non-authoritative CPN shadow. CLI composition
remains in `scripts.equation_enrichment`.

The worker invokes the external model only for owner-classified primary
recognition evidence: a non-rejected display assembly
whose detector evidence statuses are all `PROPOSED`. Inline, rejected, or
ambiguous-detector assemblies remain retained evidence and receive deterministic
`NOT_REQUESTED` proposals without a model call. If the bounded Pix2Tex process
returns a nonzero exit code after partial stdout, the invocation remains
`FAILED` and no partial LaTeX is retained. Operational transition failures
raise `EquationRecognitionError`; the repository workflow propagates that
concrete vendor-neutral exception for explicit handling at the CLI boundary
rather than manufacturing a successful result token.

Recognition remains proposal-only. A successful primary-eligible invocation can
still be assigned an auxiliary final index tier when its returned LaTeX is
malformed, prose-like, incomplete, or inconsistent with native evidence. No
proposal is accepted automatically, and equation text remains ineligible for
chunk text until review.

Recognition checkpoint inventory is classified as `NONE`, `COMPLETE_PAIR`, or
`PARTIAL` from the create-once `recognition.json`/`index.json` pair. Partial or
unsafe inventories fail closed. The reusable deferral transition changes only
an untouched `PENDING` checkpoint to `NOT_REQUESTED`; `COMPLETE`, `FAILED`, and
already-`NOT_REQUESTED` checkpoints remain unchanged, and failed checkpoints
must retain their bounded error evidence.
