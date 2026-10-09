# `ingestion.equations` implementation

`ingestion.equations` is a domain package. `AbstractEquation` is the nominal
root for immutable equation representations. `AbstractEquationImage` is an ABC
for exact format-specific image evidence; `EquationPngImage`,
`EquationJpegImage`, and `EquationWebpImage` retain exact bytes and validate
format-owned signatures. The non-instantiable `EquationImage` factory performs
bounded, closed signature dispatch and returns a concrete nominal image class.

`EquationLatex` and `EquationMathML` retain exact textual representations and
immediate source identities without implying review or acceptance.
`EquationKatex` binds exact KaTeX HTML and MathML output to the exact LaTeX
input and KaTeX version. Representation identities preserve immediate
derivation links. `EquationDerivationTransition` records one ordered success or
exceptional failure with request, result, processor, configuration, warning,
and failure identities. `EquationDerivationTrace` enforces sequence continuity,
causal closure, unique outputs, and deterministic terminal identities. Empty
traces are valid only when a request contains no equation representations or no
representation transition was requested.

Detection now belongs to `ingestion.equations.detection`. It depends on the
nominal `PageRegionRenderer` boundary. The deterministic detector requires a
renderer from its composition root and has no concrete adapter default.
Admitted COCO `Formula` detections enter through the separate
`integrations.coco.layout.equation` projection hierarchy, which maps exact
pixel geometry to source geometry and renders recognition-ready display
assemblies while retaining detector lineage. The adapter does not merge model
boxes into the native text-heuristic detector or make them authoritative.

Assembly belongs to `ingestion.equations.assembly`. The deterministic assembler
returns `EquationAssemblyResult`; the former `EquationAssemblyArtifact` name is
removed. The result retains the existing serialized fields and
`equation-assembly-artifact` stable identity namespace during migration.
Recognition request/result contracts belong to `ingestion.equations.recognition`,
while complete success and failure traces belong to
`ingestion.equations.derivation.recognition`. Recognition proposals retain
`EquationLatex` and `EquationMathML` objects rather than raw representation
strings. Their immediate source identities preserve the equation-image-to-LaTeX
and LaTeX-to-MathML derivation chain. MathML proposals retain the exact converter
processor identity and version; proposal IDs remain based on exact textual
content for compatibility. Successful traces use exact equation-image IDs as
roots and record separate image-to-LaTeX and LaTeX-to-MathML transitions.
Effect-level request/result correlation remains on the derivation result and its
compact durable record rather than masquerading as an equation representation.

Compact retrieval records belong to `ingestion.equations.index`. Recognition
checkpoint transitions belong to `ingestion.equations.recognition.checkpoint`,
and create-once recognition/index/derivation file inspection belongs to
`ingestion.equations.publication`. New publications contain the complete set;
validated recognition/index pairs remain identifiable as legacy evidence.
`EquationPublicationRequest` binds four named members and removes positional
path/content coupling before the filesystem adapter boundary. The former flat
`projectkoios.ingestion.equation_enrichment` module no longer exists. The
`scripts.equation_enrichment` composition command remains an operational CLI,
not a domain owner.

Detector behavior version 2 retains the fixed per-block inline ambiguity bound.
When a text block contains more inline-shaped matches than that bound, the
exact source block remains prose, no partial candidate subset is promoted, and
a deterministic `equation.inline_candidate_limit` warning records the observed
count and configured maximum. The detector does not raise the bound, split or
synthesize source geometry, or silently truncate candidate evidence.

Other equation selection, rendered-result validation, bounds, and identities
remain deterministic.
