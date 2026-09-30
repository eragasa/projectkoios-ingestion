# Canonical clean transcript

## Status and ownership

This owner-internal prototype is implemented by `projectkoios-ingestion`. It is
an automated, evidence-conservative projection for retrieval and navigation. It
is not human-proofread, scientifically validated, semantically corrected, or
publication-ready.

The prototype has one format and one action family:

```text
CleanTranscriptRequest
    → DeterministicCleanTranscriptProjector
    → CleanTranscript
```

There are no compatibility generations, schema variants, version-selected
contracts, artifact aliases, or migration readers. Git history is the only
history mechanism for replaced prototype shapes.

## Inputs and authority

A request binds exactly:

- one complete `StructuredTranscriptionResult`;
- one ordered `PageLayoutResult` per root page; and
- one immutable `CleanTranscriptConfiguration`.

The projector rejects missing, duplicated, mismatched, or cross-source inputs.
It may transform only retained textual evidence. It does not infer omitted
scientific content, repair equations, reinterpret symbols, or select among
competing scientific meanings.

## Result and identity

`CleanTranscript` is a `DataObjectActionResult`. Its `result_id` binds:

- the structured-transcription and ordered layout identities;
- source, document, and source-byte identities;
- all ordered page, included-block, and exclusion identities;
- every dehyphenation decision, page-number classification,
  publisher-front-matter classification, and private-use-glyph finding;
- exact consolidated text digest and UTF-8 length;
- deterministic warnings and automated status;
- projector name and version as producer provenance; and
- the exact configuration digest.

Every owned nested identity binds its exact shape and content. Changing any
bound value changes the corresponding identity. Producer versions identify the
implementation that made a result; they do not select a compatible format.

## Evidence retention

Every eligible source text block is represented exactly once as either:

1. an included block retaining exact raw text and source spans; or
2. a typed exclusion retaining the same evidence and its decision identity.

Transformations annotate included records and never replace retained raw text.
The result retains typed evidence for dehyphenation, page-number decisions,
publisher front matter, and private-use glyphs.

A line-ending hyphen is not sufficient evidence for joining words. Joining
requires positive bounded lexical evidence. Insufficient or conflicting
evidence preserves the break conservatively. Numeric text is excluded as a
page number only with printed-label evidence or recurring margin-sequence
evidence; margin position or numeric shape alone is insufficient.

Publisher material remains included unless an explicit configuration policy
names its typed classification. Private-use glyphs remain present with exact
findings and warnings.

## Deterministic batch planning and materialization

The canonical command family is:

```text
koios-plan-pdf-transcripts-batch
koios-compose-pdf-transcripts-batch
```

The planner publishes a strict durable plan whose exact field set is
`plan_id`, `configuration`, `extraction_low_text_threshold`, and `items`.
Unknown, missing, or duplicated JSON members fail closed. Plan and item
identities bind every serialized input plus the projector producer identity.

The composer preserves durable-plan preflight, source and predecessor hash
checks, symlink rejection, bounded reads, and all-or-none publication. It
publishes exactly:

```text
derived/transcription/
├── audit.json
├── clean.json
├── clean.txt
├── manifest.json
└── reference-evidence.json
```

An identical existing set is verified byte-for-byte and reported unchanged.
An incomplete, unsafe, or different set is never relabeled, repaired, or
overwritten. The manifest identity binds its exact content, all reconstructible
intermediate result identities, all persisted hashes, output path, status,
limitations, and producer provenance.

## Audit

The derivation audit verifies exact source and extraction lineage, registered
transitive dependencies, raw text and spans, page membership and order,
one-time source-block accounting, decision links, consolidated-text
reconstruction, and result identity. Passing audit establishes internal
derivation consistency only.

## Offline deterministic verifier

Run from a clean committed checkout with the already provisioned Python and the
checkout source first on `PYTHONPATH`:

```text
PYTHONPATH="$PWD:$PWD/src/python" \
  /path/to/provisioned/python scripts/verify_clean_transcript.py
```

Inputs are the selected Git worktree, the committed verifier/source files, and
one committed PDF fixture (default `tests/fixtures/pdf/equations.pdf`). The
verifier reads only Git metadata and fixture/source bytes, performs no network
or cache operation, writes no files, and emits one JSON summary to stdout.

It stops if inputs are untracked or differ from `HEAD`, the fixture is unsafe or
larger than 16 MiB, imports do not resolve under the selected checkout,
projection or serialization differs across exact replay, a removed top-level
format key appears, or the transitive derivation audit fails. Normal ingestion
limits also apply, including the 512-page clean-transcript bound. A passing run
does not establish extraction accuracy or scientific validity.
