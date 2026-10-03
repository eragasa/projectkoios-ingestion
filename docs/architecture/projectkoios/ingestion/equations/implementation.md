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
causal closure, unique outputs, and deterministic terminal identities.

Detection now belongs to `ingestion.equations.detection`. It depends on the
nominal `PageRegionRenderer` boundary. The deterministic detector requires a
renderer from its composition root and has no concrete adapter default.

Detector behavior version 2 retains the fixed per-block inline ambiguity bound.
When a text block contains more inline-shaped matches than that bound, the
exact source block remains prose, no partial candidate subset is promoted, and
a deterministic `equation.inline_candidate_limit` warning records the observed
count and configured maximum. The detector does not raise the bound, split or
synthesize source geometry, or silently truncate candidate evidence.

Other equation selection, rendered-result validation, bounds, and identities
remain deterministic.
