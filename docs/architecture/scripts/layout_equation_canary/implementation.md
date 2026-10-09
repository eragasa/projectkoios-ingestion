# `scripts.layout_equation_canary` implementation

The repository-only module records whether detector invocation, strict output
parsing, generic formula-category admission, equation projection, source-region
assembly, and recognition were actually evaluated for each private canary page.

`execute_layout_equation_canary_downstream` accepts an exact
`CocoLayoutRegionAdmissionResult`. It returns empty downstream evidence when the
formula category is empty or requires escalation and calls projection, assembly,
and recognition only when that exact category is admitted. The returned
projection must bind the same supplied admission result; admission from one
result cannot authorize a projection derived from another. Returned evidence
must retain projection-to-assembly and assembly-to-recognition lineage.

`LayoutEquationCanaryPageResult` rejects impossible stage combinations. Failed
invocation or invalid parsing leaves later stages not evaluated. Formula-category
escalation leaves projection, assembly, and recognition not evaluated and cannot
carry downstream identities or counts. An independently verified empty formula
category records zero completed counts without creating downstream artifacts.
Admitted formula pages must report exact stage counts: projected candidates plus
projection exclusions cover every admitted formula, assembly count equals
projected candidate count, and recognition proposal count equals assembly count.
Recognition counts are also partitioned exactly into `proposed`, `failed`, and
`not_requested` dispositions. A completed recognition action that returns only
`not_requested` evidence does not manufacture evaluated recognition coverage.

`summarize_layout_equation_canary_pages` reports coverage rather than accuracy.
A formula-bearing page stopped by category escalation, excluded from projection,
or retained as `not_requested` recognition evidence is not fully evaluated.
A page is evaluated only when every admitted formula is projected and has a
`proposed` recognition result. Some, but not complete, proposed coverage yields
`partially_evaluated`; zero proposed coverage yields `not_evaluated`. Any
admitted formula-bearing page that fails a downstream operation or carries a
failed recognition proposal yields `failed`.
The summary reports admitted, projected, excluded, proposed, failed, and
not-requested formula totals independently.

`verify_layout_equation_canary_document` strictly reconstructs bounded page
results, re-derives the summary, verifies page-to-record identity and status
bindings, and rejects downstream identities after a fail-closed stop. Every
admitted or empty formula category additionally requires externally supplied
typed region-admission evidence. Each completed non-empty stage must match the
corresponding trusted projection, assembly, or recognition identity and count.
Recognition disposition counts are re-derived from the exact typed recognition
artifact; failed and not-evaluated stages must not carry that stage's identity. Top-level
detector-resource, preprocessing, original-size-order, and completed-recognition
processor identities are also re-derived from trusted evidence. This prevents a
self-consistent result document from manufacturing evaluated coverage or
substituting resource lineage.

The verified document remains non-authoritative capability evidence. It cannot
select a layout, accept a transcription, or authorize publication.
