# Figure-relevance structural path map

This is the reviewed source inventory for the figure-relevance hierarchy
migration. Paths are relative to `src/python/projectkoios/ingestion`. Removed
paths are not retained as aliases or re-export facades.

| Removed path and owner | Direct owner path |
|---|---|
| `figure_relevance.py`: contract and configuration versions | `figures/relevance/constants.py` |
| `figure_relevance.py`: hard ceilings | `figures/relevance/limits/definition.py` |
| `figure_relevance.py`: `FigureRelevanceLimitError` | `figures/relevance/limits/error.py` |
| `figure_relevance.py`: `FigureRelevanceLevel` | `figures/relevance/level.py` |
| `figure_relevance.py`: `FigureRelevanceStatus` | `figures/relevance/status/result.py` |
| `figure_relevance.py`: `FigureRelevanceFailureKind` | `figures/relevance/kind/failure.py` |
| `figure_relevance.py`: `FigureRelevanceResourceIdentityKind` | `figures/relevance/identity/resource/kind.py` |
| `figure_relevance.py`: `FigureRelevanceScore` | `figures/relevance/score.py` |
| `figure_relevance.py`: `FigureRelevanceConfidence` | `figures/relevance/confidence.py` |
| `figure_relevance.py`: `FigureRelevanceResourceIdentity` | `figures/relevance/identity/resource/model.py` |
| `figure_relevance.py`: `FigureRelevanceProcessorIdentity` | `figures/relevance/identity/processor.py` |
| `figure_relevance.py`: `FigureRelevanceConfiguration` | `figures/relevance/configuration.py` |
| `figure_relevance.py`: `FigureRelevanceSelection` | `figures/relevance/selection.py` |
| `figure_relevance.py`: `FigureRelevanceRequest` | `figures/relevance/request.py` |
| `figure_relevance.py`: `FigureRelevanceProposal` | `figures/relevance/proposal.py` |
| `figure_relevance.py`: `FigureRelevanceWarning` | `figures/relevance/warning.py` |
| `figure_relevance.py`: `FigureRelevanceFailure` | `figures/relevance/failure.py` |
| `figure_relevance.py`: `FigureRelevanceSelectionResult` | `figures/relevance/result/selection.py` |
| `figure_relevance.py`: `FigureRelevanceResult` | `figures/relevance/result/aggregate.py` |
| `figure_relevance.py`: `build_figure_relevance_cache_key` | `figures/relevance/cache/identity.py` |
| `figure_relevance.py`: request identity derivation | `figures/relevance/identity/request.py` |
| `figure_relevance.py`: proposal identity derivation | `figures/relevance/identity/proposal.py` |
| `figure_relevance.py`: selection-result identity derivation | `figures/relevance/identity/selection.py` |
| `figure_relevance.py`: aggregate-result identity derivation | `figures/relevance/identity/result.py` |
| `figure_relevance.py`: request relation validation | `figures/relevance/validation/request.py` |
| `figure_relevance.py`: proposal evidence validation | `figures/relevance/validation/proposal.py` |
| `figure_relevance.py`: selected-candidate validation | `figures/relevance/validation/selection.py` |
| `figure_relevance.py`: aggregate-result validation | `figures/relevance/validation/result.py` |
| `figure_relevance.py`: bounded primitive and retained-size validation | `figures/relevance/validation/value.py` |
| `figure_relevance_processor.py`: `FigureRelevanceProcessor` | `figures/relevance/processor/base.py` |

`FigureRelevanceContract` was a static utility container rather than a domain
record or injectable boundary. It has no replacement class: each identity and
validation operation now lives in the direct owner listed above.

## Semantic review

- Figure relevance is owned by the existing plural `figures/` domain rather
  than by a new root-level compound namespace.
- Request, selection, proposal, result, processor, identity, validation, and
  cache responsibilities use direct role leaves.
- Resource identity and its provenance kind share
  `identity/resource/`; `model.py` names the immutable record without creating
  a redundant `resource/resource.py` path.
- The aggregate action result uses `result/aggregate.py` to distinguish it from
  the per-selection result without repeating `result/result.py`.
- Hard ceilings and their error use the plural `limits/` owner.
- Package initializers are docstring-only ownership markers. Consumers import
  definitions from their direct leaves; neither the new hierarchy nor the
  ingestion root supplies compatibility exports.
- Contract versions, field order, stable identity inputs, retained evidence,
  validation bounds, immutable records, proposal-only semantics, and serialized
  bytes are unchanged.
- No processor implementation, backend selection, acceptance decision,
  Workflow behavior, transcript behavior, Pipeline design, or operational
  execution is introduced or changed.
