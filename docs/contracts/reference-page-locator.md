# Reference page locator

## Contract metadata

| Field | Value |
|---|---|
| Contract ID | `projectkoios.ingestion.reference-page-locator` |
| Target version | `0.1.0` |
| Status | Proposed |
| Owner | `projectkoios-ingestion` |
| Acceptance authority | Project Koios operator after ingestion and workflow-consumer review |
| Dependency | `projectkoios.ingestion.reference-evidence@0.1.0` and clean transcript generation 1 |
| Consumer | `projectkoios.workflow.reference_review` candidate adapter |
| Effective baseline | None while proposed |

## Scope

The locator performs bounded mechanical page navigation over one exact
`CleanTranscriptPage`. It binds a reusable complete reference-evidence record,
clean-transcript artifact, page identity/index, and a sorted set of topic-anchor
alternatives. It does not read a PDF, discover a source, run OCR, retain page
text, assess a claim, accept evidence, or authorize publication.

## Matching

Matching uses Unicode NFKC normalization followed by case folding. Alphanumeric
runs are tokens and every other character is a boundary. An anchor matches only
when its complete normalized token sequence appears contiguously in the page
token sequence. Therefore `mass` does not match `biomass`, while
`effective mass` matches `effective-mass`.

Anchor inventories are nonempty, sorted, unique, and bounded to 32 alternatives,
256 characters and 32 normalized tokens per alternative. Alternatives that
normalize to the same token sequence are rejected. Page text is bounded to
2,000,000 characters before matching.

## Lineage and result

Before matching, the checker requires exact agreement among the reference
record and transcript for:

- transcript artifact, structured-transcription, and layout identities;
- complete transcript text SHA-256 and byte length;
- extracted document identity; and
- source blob and content SHA-256 identities.

The request locator holds the bounded search phrases needed for the in-memory
check. The result does not embed that locator or its phrases: it retains only
content-derived locator, lineage, page, and topic-anchor identities; page text
digest and byte length; the complete matched/unmatched anchor-identity
partition; status; processor and contract versions; and mandatory limitations.
Page text, search phrases, quotation text, source paths, credentials, and
private locators are excluded from the result.

## Authority limits

`match` means only that one complete normalized token phrase was mechanically
found on one exact extracted page. It does not establish extraction accuracy,
semantic claim support, quotation accuracy, source authority, scientific
validity, human acceptance, rights clearance, or publication suitability.

The ingester owns parsing and locator evidence. Workflow may consume the result
as typed non-authorizing input. Review and publication remain separate human-
owned operations.
