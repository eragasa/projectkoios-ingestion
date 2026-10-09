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
- deterministic tests marked `benchmark` as a separately visible regression
  gate;
- the complete pytest suite, including those benchmark regressions;
- the NumPy-docstring Sphinx API build under `docs/sphinx/`, with warnings
  treated as errors;
- source and wheel builds;
- installation and import from the built wheel in a clean environment; and
- whitespace validation.

Formatting coverage is deliberately partial. Existing ingestion modules outside
the reference-evidence slice predate the current Ruff formatter and are not
silently reformatted by this CI introduction. Lint, typing, tests, and packaging
still cover the full repository. Expanding formatter ownership requires a
separate reviewed baseline-only change.

Hierarchy changes also follow the maintained [code smell review](code-smell-review.md).
Its smoke gates enforce objective package-shape rules in migrated scopes, while
semantic ownership, action boundaries, and unstable API terminology receive an
explicit human-readable review in each pull request.

These checks verify software contracts only. The `benchmark` marker identifies
frozen, deterministic regression evidence; it does not imply a timing benchmark
or private-corpus quality claim. Private-corpus detector baselines and reports
remain outside Git. The checks do not establish extraction accuracy, OCR
adequacy, claim support, scientific validity, rights clearance, human
acceptance, or publication authority. Real Tesseract execution remains an
explicitly configured external smoke test and may be skipped when its fixture is
not configured.
