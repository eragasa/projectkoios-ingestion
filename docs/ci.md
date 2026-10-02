# Continuous integration

The hosted workflow runs on Python 3.14 using the committed `uv.lock`. The
`projectkoios==0.0.0` dependency is pinned to Git commit
`233f36900b9b44c943ecc5e27f2968ad4bee97ad`; CI does not resolve a moving
branch.

Every pull request and `master` push runs:

- formatting checks for the reference-evidence, page-locator, and
  claim-candidate slice;
- Ruff lint over all production and test Python;
- mypy over all production Python;
- the complete pytest suite;
- source and wheel builds;
- installation and import from the built wheel in a clean environment; and
- whitespace validation.

Formatting coverage is deliberately partial. Existing ingestion modules outside
the reference-evidence slice predate the current Ruff formatter and are not
silently reformatted by this CI introduction. Lint, typing, tests, and packaging
still cover the full repository. Expanding formatter ownership requires a
separate reviewed baseline-only change.

These checks verify software contracts only. They do not establish extraction
accuracy, OCR adequacy, claim support, scientific validity, rights clearance,
human acceptance, or publication authority. Real Tesseract execution remains an
explicitly configured external smoke test and may be skipped when its fixture is
not configured.
