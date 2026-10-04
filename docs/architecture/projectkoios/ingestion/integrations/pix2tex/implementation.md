# Pix2Tex integration implementation

`Pix2TexCliEquationRecognizer` validates and retains exact executable and model
resource identities. It stages exact rendered PNG bytes in a private temporary
directory and invokes the executable without a shell. One invocation receives a
concrete `Pix2TexInvocationRequest` and either returns a concrete
`Pix2TexInvocationResult` or raises `Pix2TexInvocationError`.

Before invocation, processor version 5 applies a deterministic primary-evidence
gate. It retains all assemblies but invokes Pix2Tex only for proposed display
assemblies with 4–64 native-text characters, at most 14 native words, at most
three grouped candidates, and an opaque 8-bit RGB PNG containing at most two
foreground bands. Two-band regions touching a vertical edge remain retained but
are not requested. Ineligibility reasons are preserved as proposal warnings.
These bounds screen overbroad, context-contaminated, truncated, and weak visual
evidence; they do not establish mathematical correctness.

Processor version 5 also records high-precision output warnings for brace,
`\left`/`\right`, and environment mismatches; excessive spacing; implausible
output expansion; duplicated equation labels; and native equalities absent from
the proposal. Warnings never accept output or make it chunk-text-eligible.
Symbol substitutions can remain syntactically valid, so unattended execution
still requires separate evidence that the configured recognizer is suitable.

## Corpus suitability and deferral

Suitability is a property of an exact processor identity and a frozen evidence
population, not of the Pix2Tex package name. For the prepared semiconductor
reference corpus, two 30-item canaries completed without invocation failures.
The matched second canary improved isolated-region quality to 28 of 30, but 14
of 30 recognition outputs still had review concerns. Across all 60 outputs,
deterministic processor-version-5 warnings detected 18 of 33 audited concerns;
15 semantic or visual concerns remained undetectable. Observed warning precision
was `0.9473684210526315`, while observed concern recall was
`0.5454545454545454`.

That evidence closes this configured Pix2Tex path as unsuitable for unattended
execution on this corpus. Operational success, syntactic validity, successful
MathML conversion, and absence of a warning are not acceptance evidence. The
remaining queue must not be expanded automatically or placed on an indexing
critical path.

The closure is retained as the checksummed deferral inventory
`reference-multimodal-equation-recognition-deferral-inventory:sha256:a3dca8416c037f578624bec3702db1b63f5dc78d91264356bfb0a531bdd558a1`.
It covers all 1,906 proposed-primary assemblies: 662 isolated regions are
`deferred_future_recognizer`, and 1,244 contaminated, non-equation, overbroad,
or truncated regions are `retained_not_eligible`. Every record remains
unreviewed, unaccepted, review-required, and chunk-text-ineligible. The rendered
image, source binding, disposition, byte count, and digest remain available for
replay or a future recognizer.

Reading-transcript composition may proceed independently of recognition. It may
retain native text, separately selected OCR evidence, figure and table evidence,
and equation-region image references. It must not insert generated LaTeX or
MathML into transcript text, infer replacement text, accept an equation, or
make equation recognition chunk-text-eligible. The earlier deterministic
three-book evidence collection,
`reference-reading-transcript-collection:sha256:b962b470c8e55d5ea715afe1819c54c022107a4c5bf6f5906d745f6427062825`,
is superseded by the recognition-independent collection described below. Its
1,906 equation records remain retained historical evidence with no recognized
LaTeX or MathML.

Legacy reading projections must apply the same independence rule. Recognition
output quality is not an equation-region selection policy. In the retained
Neaman run, detection produced 1,821 candidates and 1,229 assemblies. The
recognition request selected 457 primary-evidence regions, but the legacy
reading projection retained only 46: 25 records promoted by the output-oriented
index tier and 21 failed invocations. The corrected projection retains all 457
selected region images and native source bindings, discards every historical
LaTeX and MathML proposal, and leaves 771 auxiliary plus one rejected assembly
in the selection inventory. A recognizer failure therefore no longer removes
primary visual evidence, and recognizer output quality no longer determines
whether a region is represented.

The three-book preparation now also has a recognition-independent equation
selection inventory,
`reference-equation-evidence-selection-inventory:sha256:1ce4f8c68241e3dee14085c3673405f06ba321e7938e955db1a75a1cd1734a00`.
It classifies all 5,360 assemblies directly from detector and assembly evidence:
1,906 are selected primary evidence and 3,454 remain retained auxiliary evidence.
It does not read recognition results and retains no recognized text. The
resulting transcript collection is
`reference-reading-transcript-collection:sha256:5e2da983eedbacc90943feb167ace26b349a252c49284dc97f8bc03e4ccc148f`.
It covers the same 2,031 pages, 1,906 equations, 947 figures, and 872 tables as
the previous collection. Its semantic comparison passed with validation
`reference-reading-transcript-validation:sha256:ae4c6994643543ca8522f6cb7fdb91657b38b01429c5dc0a24e62ff8c3ea646a`.

The same deterministic correction was applied to `doc-01` through `doc-05`.
The authoritative nine-document coverage inventory is
`reference-reading-corpus-coverage:sha256:3b5f51b9bf48a9e0f02ffb0b4738316399768138589bfa299b6bf29bee2ebd80`,
validated by
`reference-reading-corpus-coverage-validation:sha256:374c79280da6727b1d6e9cbe7be9559c66428abb1bf386f64e7cf8257e949996`.
It covers 6,198 pages with 4,648 unique equation references, 2,256 figure
references, and 872 table references. Its recognized-equation-text count is
zero. Every equation reference is explicitly unreviewed, unaccepted,
review-required, and chunk-text-ineligible. The prior coverage inventory is
retained with an immutable supersession marker.

Reopening recognition requires a new processor identity and a new frozen,
representative canary with output correctness reviewed independently of crop
quality. A replacement recognizer must demonstrate that semantic symbol errors
are controlled; adapter success and deterministic syntax warnings alone are
insufficient. Prior Pix2Tex proposals remain historical evidence and must not
be silently accepted, corrected, or substituted.

## Invocation failure boundary

A nonzero exit invalidates the complete invocation. Diagnostic bytes remain
bounded, and stdout is discarded before UTF-8 decoding or LaTeX parsing. The
adapter translates successful outputs into vendor-neutral recognition proposals
and returns `EquationRecognitionArtifact`. Proposals remain automated,
unreviewed, unaccepted, and chunk-text-ineligible.
