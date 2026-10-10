# Current-schema page-projection observation

`current-schema-v1.json` is sanitized cross-repository test evidence projected from one real typed synthetic `PageProjectionResult`. It is not a production wire format, JSON codec, compatibility promise, publication record, or replacement for the typed Python contract.

The synthetic source contains one paragraph, one admitted unique figure caption, and canonical table/equation blocks. The page projector emits only the paragraph and configured caption; media, table, and equation content remain excluded.

## Frozen payload

- Fixture kind: `projectkoios.ingestion.page-projection-observation`
- Fixture schema: `1`
- Byte representation: sorted-key compact UTF-8 JSON with no terminal newline
- Byte length: `2554`
- SHA-256: `9e725777ebb87f5a9fc69ebbcb64d69c98aabd205a3e92c95840c13fac538c8f`
- Git blob OID: `16ccea4aef4154531d2963f9cca7c41280ee19c7`
- Fixture-producing commit: `b643f111436b40264e8c2343b1b20e8875f637d7`
- Typed producer: `PageProjectionObservationFixture` in `tests/projectkoios/ingestion/page/projection/fixture.py`
- Producer verification: `test__page_projection_observation__matches_frozen_fixture`

This README was added after the immutable fixture-producing commit so it can name that commit exactly without changing the JSON bytes or blob OID.
