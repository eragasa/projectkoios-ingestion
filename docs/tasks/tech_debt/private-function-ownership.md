# Private function ownership

## Status

Open. Incremental enforcement began after the function-smell review at commit
`7f255624bb1cce5fcd5126a55369f4f00fbc7f5e`.

## Problem

The review found 340 underscore-prefixed member functions and 105 cross-module
imports of underscore-prefixed functions. A blanket rename would expose
implementation details without assigning semantic ownership. A repository-wide
rewrite would also combine unrelated adapter, storage, layout, OCR, table, and
transcript risks.

Static utility containers are the clearest ownership smell:

- `TesseractOCRContract`: 23 private static methods;
- `CleanTranscriptContract`: 23 private static methods;
- `LayoutContract`: 13 private static methods; and
- `LayoutGeometryContract`: 5 private static methods.

## Policy

The smoke suite maintains two incremental registries:

- `_NO_PRIVATE_MEMBER_FUNCTION_SCOPES` for domains whose classes have no private
  member functions; and
- `_NO_CROSS_MODULE_PRIVATE_IMPORT_SCOPES` for domains that do not consume
  private members from another module.

A registered scope may not regress. Add a scope as soon as its applicable debt
is removed. Do not preserve a private name across module boundaries, and do not
make a helper public merely to satisfy the test. Give it a semantic owner and
name, co-locate it with its consumer, or remove it.

## Sequence

1. Rename or co-locate article-structure and figure-relevance private functions
   that are consumed by sibling defining leaves, then register those scopes for
   private-import enforcement.
2. Decompose table-structure validation and derivation utility containers before
   registering that domain for private-member enforcement.
3. Review Ingestion Base private validation hooks explicitly; preserve genuine
   polymorphic hooks only through a named contract rather than a silent
   exception.
4. Handle layout and Tesseract as separate behavior-preserving reductions with
   focused replay and adapter safety tests.
5. Handle clean transcript only under
   `docs/tasks/tech_debt/clean-transcript-module-size.md`; no move-only split is
   permitted.

## Completion evidence

Each scope migration must include direct defining-leaf imports, no cross-module
private imports, no private member functions where registered, focused behavior
or replay evidence, full tests, type checking, documentation, clean-wheel
verification, and mutation evidence that the new smoke registration rejects a
regression.
