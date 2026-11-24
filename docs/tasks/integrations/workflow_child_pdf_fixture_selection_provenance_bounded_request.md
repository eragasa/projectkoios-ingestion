# Ingestion real-journal-article PDF fixture selection and provenance bounded request

## Status and authorization boundary

This document is a **documentation-only request for review**. It does not select,
copy, admit, stage, commit, publish, process, or execute either candidate PDF.
It does not authorize a fixture implementation, Workflow SDK adoption, child
Workflow execution, identity promotion, scientific use, release, or deployment.

The exact documentation-request base is the clean Ingestion checkpoint:

```text
df29924c72722fbd2eaef524ba8415cdb31c894f
```

The request exists in the isolated documentation worktree:

```text
worktree: /Users/eugene/worktrees/projectkoios-ingestion/workflow-child-pdf-fixture-request
branch:   docs/workflow-child-pdf-fixture-request
```

The sole request-document path is:

```text
docs/tasks/integrations/workflow_child_pdf_fixture_selection_provenance_bounded_request.md
```

This request proposes a later, separately authorized fixture-admission slice.
Review acceptance authorizes no edit to that future slice and no copy of the
private local candidate assets.

## Repository ownership boundary

Ingestion owns source ingestion and document processing. Under the proposed
split, Ingestion would own:

- the exact committed pilot fixture bytes;
- fixture attribution and acquisition provenance;
- deterministic local fixture verification; and
- later, separately gated expected Ingestion outputs.

References would remain the owner of bibliographic candidate/acquisition
evidence and would supply an `unaccepted-candidate` source-evidence crosswalk.
References would not become a shared binary fixture store. Ingestion would not
promote a References identity, citekey, relevance judgment, scientific claim,
or publication status.

Cross-repository routing and product architecture remain Bootstrap-owned. This
request does not decide the Workflow runtime, SDK promotion, registry,
scheduler, persistence, retry, aggregate-parent, or production adoption model.

## Exact requested decision

The future admission slice should select exactly two real, small,
redistributable journal-article PDFs as hermetic Ingestion-owned test fixtures:

1. the exact Jiang et al. 2025 publisher-version bytes identified below; and
2. the exact Dick and Dahm 2025 publisher-version rendition identified below.

Two distinct articles are required because a later workflow pilot intends to
test sibling failure isolation, aggregate-parent completion, and exact-existing
replay. This admission slice does **not** run that pilot and does not create its
expected transcript outputs.

The alternative one-article scope is rejected for this request because it
cannot provide meaningful two-item batch or sibling-isolation evidence. No
third PDF may be admitted.

## External immutable request-digest protocol

This document cannot embed or authorize its own final SHA-256. After all review
corrections are complete, the final exact bytes must receive renewed Ingestion
and References review. A later, separate operator authorization must supply the
complete accepted digest under the exact external name:

```text
ACCEPTED_INGESTION_REAL_ARTICLE_FIXTURE_REQUEST_SHA256
```

The implementation agent may not infer this value from the document, current
filesystem state, a branch name, review message, abbreviated digest, nearby
manifest, or transport metadata. Recursive/self-hash placeholders are
forbidden.

Before creating the future implementation worktree, before the first and every
subsequent source edit or binary copy, before each artifact build, and before
final evidence, the implementation agent must hash this exact external path and
compare it with the operator-supplied value:

```text
/Users/eugene/worktrees/projectkoios-ingestion/workflow-child-pdf-fixture-request/docs/tasks/integrations/workflow_child_pdf_fixture_selection_provenance_bounded_request.md
```

A missing value, non-exact spelling, byte drift, path difference, digest
mismatch, or post-authorization request edit stops the slice. Changed request
bytes require renewed two-owner review and new operator-supplied authorization.

## Exact source-evidence boundary

The current private local acquisition evidence is read-only input to a future
copy operation:

```text
root: /Users/eugene/repos/projectkoios-references/.koios/candidate-assets/wannier-literature-recommendation-20260917
manifest: manifest.json
manifest SHA-256: 1b1e8fef35b38d67e22ff02776504f863a6b143bebe6031b00db1a73783adc43
manifest schema_version: 1
manifest generated_at: 2026-09-17T19:43:11.614916+00:00
manifest source_id: operatorWannierRecommendation20260917
manifest mode: private-local-candidate-source-acquisition
```

That ignored/private staging manifest is source evidence only. It is not
fixture-selection authority, canonical References identity, public catalog
admission, or a durable runtime dependency.

A future authorized implementation may read the exact staging paths only to
verify and copy the selected bytes once. Tests, builds, runtime, and later
pilots must not resolve a cross-repository path. No network retrieval,
redownload, alternate rendition, PDF rewrite, metadata normalization,
linearization, compression, page deletion, or content transformation is
allowed.

If the exact staging manifest or either exact candidate file is absent or has a
different byte count or SHA-256, implementation must stop. It may not repair the
staging area or acquire replacement bytes.

## Exact Jiang fixture evidence

The first candidate is bound to:

```text
private source file: jiang2025.pdf
future content-addressed filename:
  08156c7378832cd26f4daabb52af23fc474468881dce78c7c6e420ac6025630b.pdf
SHA-256: 08156c7378832cd26f4daabb52af23fc474468881dce78c7c6e420ac6025630b
byte size: 2268128
PDF format: PDF 1.4
physical pages: 11
encrypted: false
DOI: 10.1038/s41524-025-01835-8
source URL: https://www.nature.com/articles/s41524-025-01835-8.pdf
source version: published-version / version of record
rights: CC-BY-4.0
license URI: https://creativecommons.org/licenses/by/4.0/
identity status: unaccepted-candidate
```

Exact article identity:

```text
title: Robust Wannierization including magnetization and spin-orbit coupling via projectability disentanglement
authors: Yuhao Jiang; Junfeng Qiao; Nataliya Paulish; Weisheng Zhao; Nicola Marzari; Giovanni Pizzi
journal: npj Computational Materials
volume: 11
article number: 353
publication year: 2025
publisher: Springer Nature
copyright: © The Author(s) 2025
```

The committed attribution must state that the article is licensed under the
Creative Commons Attribution 4.0 International License and that use, sharing,
adaptation, distribution, and reproduction require appropriate author/source
credit, a license link, and an indication of changes. The exact bytes are
unmodified, so the change indication is `No changes were made to the PDF
bytes.`

The attribution must retain the article's third-party-material caveat: images
or other third-party material are included under the article license unless a
credit line indicates otherwise; uses outside an indicated license or statutory
permission require permission from the copyright holder. Fixture admission is
not a manual visual rights audit of every figure.

The anomalous XMP Crossmark `MajorVersionDate` value reported during References
review must not be used as publication-date evidence. The publisher-version
article identity and exact source acquisition evidence above are authoritative
for this fixture request.

## Exact Dick and Dahm fixture evidence

The second candidate is bound to:

```text
private source file: dickDahm2025.pdf
future content-addressed filename:
  3ab2ca08c875cb5966d580c6af631eaedec6a09a0cfca60999a20f9e7c7f0084.pdf
SHA-256: 3ab2ca08c875cb5966d580c6af631eaedec6a09a0cfca60999a20f9e7c7f0084
byte size: 4120586
PDF format: PDF 1.7
physical pages: 13
article pages: 12 plus one IOP cover/download page
encrypted: false
DOI: 10.1088/2516-1075/ae1776
source URL: https://iopscience.iop.org/article/10.1088/2516-1075/ae1776/pdf
source version: published-version / version of record
rights: CC-BY-4.0
license URI: https://creativecommons.org/licenses/by/4.0/
identity status: unaccepted-candidate
```

Exact article identity:

```text
title: Optimization of ab-initio based tight-binding models
authors: Henrik Dick; Thomas Dahm
journal: Electronic Structure
volume: 7
article number: 047001
publication year: 2025
published: 2025-11-05
publisher: IOP Publishing Ltd
copyright: © 2025 The Author(s). Published by IOP Publishing Ltd
```

The committed attribution must state that original content may be used under
CC BY 4.0 and that further distribution must retain attribution to the authors,
article title, journal citation, and DOI. It must state `No changes were made to
the PDF bytes.`

The exact rendition includes an IOP cover/download page stating that it was
downloaded from IP address `138.84.137.110` on `17/09/2026 at 20:41`, and its
metadata records a 2026-09-17 modification/download event. This rendition
provenance must be retained without treating the download address as a runtime
locator or a source identity.

The 13-physical-page versus 12-article-page distinction is provenance supplied
by reviewed evidence. The future verifier must check the 13 physical pages but
must not pretend to infer semantic article-page count from page contents.

## No scientific or identity inference

Admission of either PDF would establish only that exact licensed bytes are
available for deterministic software testing. It must not establish:

- canonical References citekeys or identity promotion;
- Search or bibliography admission;
- relevance to any research question;
- correctness of article claims;
- accepted citation support;
- proofread or scientifically valid extraction output;
- permission for model training beyond the recorded license terms;
- owner adoption of Workflow or the Workflow SDK; or
- production-publication authority.

The proposed labels `jiang2025` and `dickDahm2025` remain private acquisition
labels only. Content-addressed committed filenames prevent those labels from
becoming Ingestion or References identities.

## Exact future implementation worktree

A later, separately authorized fixture-admission implementation would use:

```text
worktree: /Users/eugene/worktrees/projectkoios-ingestion/workflow-child-pdf-fixtures
branch:   work/workflow-child-pdf-fixtures
base:     df29924c72722fbd2eaef524ba8415cdb31c894f
```

The current Ingestion worktrees must not be altered or cleaned. The future
worktree must start clean at the exact base and remain local unless a separate
push authorization is supplied.

## Exact future implementation inventory

Modify exactly one path:

```text
.gitattributes
```

Add exactly five paths:

```text
tests/fixtures/pdf/real-journal-articles/README.md
tests/fixtures/pdf/real-journal-articles/manifest.json
tests/fixtures/pdf/real-journal-articles/08156c7378832cd26f4daabb52af23fc474468881dce78c7c6e420ac6025630b.pdf
tests/fixtures/pdf/real-journal-articles/3ab2ca08c875cb5966d580c6af631eaedec6a09a0cfca60999a20f9e7c7f0084.pdf
tests/projectkoios/ingestion/fixtures/test__RealJournalArticleFixtures.py
```

There may be no other modification, addition, deletion, rename, symlink,
submodule, generated output, or mode-only change. In particular, the nested
test path requires no `__init__.py` or other directory-support file, and none
may be added.

The base contains exactly 2,388 tracked paths. Only `.gitattributes` may differ
from the base among tracked paths; the other 2,387 base-tracked paths must
remain byte-identical. Its base SHA-256 is:

```text
f798bea4b09f7bba38d7bd8967eb5bc83bda2701211c7b590ea19a5db85ad366  .gitattributes
```

The current synthetic fixture matrix remains byte-frozen, including:

```text
762c94596a17843583980dc7233d7d798b59c233c24f113b0700ee2fc4824573  tests/fixtures/pdf/README.md
8a0450026bc5965fbf57227ccdbb6c996ad79c44ba1f3406916175b3e02b0d58  tests/fixtures/pdf/manifest.json
```

The real-article directory is separate because every existing matrix PDF is
wholly synthetic and generated by `scripts/pdf_fixture_matrix.py`. The future
slice must not add either real article to that generator, README, or manifest.

## Exact Git attribute change

The future `.gitattributes` change must append exact rules covering only the new
directory:

```gitattributes
tests/fixtures/pdf/real-journal-articles/*.pdf binary
tests/fixtures/pdf/real-journal-articles/README.md text eol=lf
tests/fixtures/pdf/real-journal-articles/manifest.json text eol=lf
```

Existing attribute rules remain byte-for-byte and in their current order. The
new PDF rules prevent line-ending or filter transformations of exact licensed
bytes. The text rules make the attribution and manifest checkout-independent.
No Git LFS rule, external filter, smudge/clean command, archive substitution, or
network-backed storage may be introduced.

## Exact attribution README obligations

The future fixture README must:

- state that the directory contains two exact unmodified real journal-article
  PDFs admitted only for offline deterministic Ingestion software tests;
- include the complete article identity, citation, copyright, publisher,
  source URL, version-of-record status, DOI, exact hash, byte size, PDF version,
  physical-page facts, acquisition-evidence date, and CC BY 4.0 URI for each;
- include the Jiang third-party-material caveat;
- include the Dick/Dahm IOP cover/download-page and 13/12 page distinction;
- state `No changes were made to the PDF bytes.` for each;
- state that the source acquisition manifest is evidence, not acceptance
  authority;
- state that References identities/citekeys remain unaccepted candidates;
- include the exact non-relicensing statement below;
- state that tests perform no network access and never resolve the private
  staging path;
- distinguish fixture admission from extraction-output, scientific, citation,
  relevance, publication, Workflow-adoption, or production acceptance; and
- identify Ingestion as fixture/verification owner and References as
  source-evidence/crosswalk owner.

The exact non-relicensing statement is one source line:

```text
The repository's Apache License 2.0 applies only to Project Koios-owned code and text. It does not relicense either third-party PDF. Each PDF remains copyrighted by its stated authors and is distributed under its recorded CC BY 4.0 terms.
```

The README must not reproduce article text, abstracts, figures, or claims beyond
what is necessary for citation, attribution, rights, and deterministic fixture
identity.

## Exact manifest contract

The future `manifest.json` must be canonical UTF-8 JSON with LF ending, two-space
indentation, the exact object-key order defined below, no duplicate keys, no
non-JSON values, and exactly one final newline. It must not include its own
hash.

Its exact top-level keys are:

```text
schema_version
fixture_purpose
owner
source_evidence
records
```

Required exact top-level values are:

```text
schema_version: 1
fixture_purpose: workflow-child-per-pdf-real-article-pilot
owner: projectkoios-ingestion
```

`source_evidence` must contain exactly:

```text
owner: projectkoios-references
identity_status: unaccepted-candidate
source_id: operatorWannierRecommendation20260917
mode: private-local-candidate-source-acquisition
manifest_generated_at: 2026-09-17T19:43:11.614916+00:00
manifest_sha256: 1b1e8fef35b38d67e22ff02776504f863a6b143bebe6031b00db1a73783adc43
acceptance_authority: false
runtime_dependency: false
```

`records` must be a two-element array ordered first by the Jiang SHA-256 and
then by the Dick/Dahm SHA-256. Each record must use one exact, record-specific
shape with these keys:

```text
relative_path
sha256
byte_size
pdf_version
physical_page_count
article_page_count
encrypted
doi
title
authors
journal
volume
article_number
publication_year
published_date
publisher
copyright
source_url
source_version
retrieval_date
license_spdx
license_uri
attribution
exact_bytes_unmodified
change_statement
third_party_material_caveat
rendition_note
identity_status
scientific_acceptance
```

Values must match the exact evidence in this request. `authors` is an ordered
array of full author names. `article_page_count` is 11 for Jiang and 12 for
Dick/Dahm. `published_date` is `null` for Jiang because this request does not
carry a separately accepted exact publication day; it is `2025-11-05` for
Dick/Dahm. `retrieval_date` is `2026-09-17` for both records: it is the bounded
local acquisition date supported by the staging evidence, not a fabricated
per-file timestamp. `third_party_material_caveat` is the exact bounded Jiang
caveat and `null` for Dick/Dahm. `rendition_note` is `null` for Jiang and
records the exact IOP cover/download-page provenance for Dick/Dahm. Both records
use:

```text
license_spdx: CC-BY-4.0
license_uri: https://creativecommons.org/licenses/by/4.0/
exact_bytes_unmodified: true
change_statement: No changes were made to the PDF bytes.
identity_status: unaccepted-candidate
scientific_acceptance: false
```

The manifest may not contain a local absolute path, credential, IP address
except inside the reviewed Dick/Dahm rendition note, mutable branch, runtime
registry locator, Workflow identity, extraction output, generated transcript,
model judgment, or canonical References citekey.

## Exact future copy protocol

Before each future binary copy, the implementation agent must:

1. verify the externally supplied accepted request digest;
2. verify the private staging manifest exact SHA-256;
3. parse its exact schema and require the candidate record's DOI, relative path,
   source URL, source version, rights status, hash, byte size, page count,
   encryption state, and identity-check evidence;
4. hash and size the source PDF before opening it;
5. confirm it is a regular file and not a symlink;
6. copy bytes without transformation to the content-addressed target;
7. `cmp` source and target bytes;
8. rehash and resize the target; and
9. fail closed and remove only the newly created target on any mismatch.

No command may fetch a URL. No fallback source, alternate DOI resolution,
browser cache, private corpus search, conversion, repair, recompression, or PDF
writer may be used.

The two targets must not be staged or committed until all source, target,
attribution, manifest, test, license, and inventory checks pass. Copy authority
would not itself authorize staging or commit.

## Exact future test module

`tests/projectkoios/ingestion/fixtures/test__RealJournalArticleFixtures.py`
must contain exactly six non-parameterized top-level tests and no generated or
parameterized test cases. It may use deterministic standard-library modules and
the already locked PyMuPDF dependency. It must not use network, subprocess,
shell, browser, DOI resolver, filesystem mutation, temporary copies, dynamic
import, reflection, `Any`, unchecked casts, or private cross-repository paths.

The module must contain exactly one PyMuPDF untyped-boundary exception on its
single shared open call, with this exact statement shape:

```python
document = pymupdf.open(path)  # type: ignore[no-untyped-call]
```

This is the only permitted `type: ignore` in the module and the only newly
added ignore or cast in the future slice. Strict MyPy must retain unused-ignore
checking so this bounded exception fails if it becomes obsolete. The exception
admits no untyped value into owned manifest or provenance structures.

The six tests must separately prove:

1. the real-article directory contains exactly the README, manifest, and two
   content-addressed regular PDF files, with no symlink or extra;
2. the manifest has exact canonical UTF-8/LF bytes, exact key sets, schema,
   owner, purpose, source-evidence record, two-record order, no duplicate key,
   and no self-hash;
3. each record has complete exact citation, copyright, CC-BY-4.0 URI, source,
   acquisition/version/change/third-party provenance and retains
   `unaccepted-candidate` / `scientific_acceptance: false` boundaries, while
   the README contains the exact Apache-2.0 non-relicensing statement;
4. each committed PDF's content-addressed filename, SHA-256, byte size, `%PDF-`
   header, manifest identity, and exact-unmodified claim agree;
5. bounded local PyMuPDF inspection reports unencrypted inputs, PDF 1.4/11
   physical pages for Jiang, PDF 1.7/13 physical pages for Dick/Dahm, and no
   embedded file attachments; the 12 Dick/Dahm article-page count remains an
   explicit provenance fact rather than content-derived acceptance; and
6. `.gitattributes` contains the exact nested binary/text rules, neither new
   Python/documentation file contains downloader/network or private staging
   imports, and the fixture directory is absent from `src/python` and the
   configured package-source inventory.

Actual wheel and sdist membership is proved only by the post-build artifact
gate below. Ordinary pytest runs before artifacts exist, may not build them,
and must not claim to inspect them.

The tests must never compare extracted article prose, scientific content, or
expected transcripts. Those outputs belong to a later pilot-execution slice.

## Baseline and expected validation counts

At exact base `df29924c72722fbd2eaef524ba8415cdb31c894f`, read-only evidence is:

```text
pytest: 1503 collected; 1501 passed; 2 skipped
benchmark gate: 27 passed; 1476 deselected
strict page-projection scope: 15 files, clean
strict publication scope: 21 files, clean
exact distinct strict union: 36 files, clean
```

The future six-test admission slice must produce exactly:

```text
pytest: 1509 collected; 1507 passed; 2 skipped
benchmark gate: 27 passed; 1482 deselected
new fixture tests: 6 passed
```

The two existing strict scopes remain byte-frozen and clean at 15 and 21 files.
The new fixture test must also pass a separate strict MyPy invocation with
exactly the one localized PyMuPDF `no-untyped-call` exception defined above,
unused-ignore checking enabled, and no other ignore, cast, or relaxation. The
exact distinct strict evidence union therefore contains 37 files.

The broader existing non-strict CI typing command covers 1,183 tracked Python
files and currently reports exactly two pre-existing `import-not-found` errors
for `snakes.nets` and `snakes.typing` in `cpn/equation_recognition.py`. The
future slice may neither claim that baseline is clean nor add, suppress, or
change any error. It must record exact unchanged diagnostics separately from
the clean strict scopes.

## Exact artifact baseline and semantic sdist rule

All four clean artifact builds use the exact environment below. Runs 1 and 2
use `PYTHONHASHSEED=1` and `PYTHONHASHSEED=2`, respectively, for both the
pre-slice base and post-slice candidate:

```text
SOURCE_DATE_EPOCH=1791748419
TZ=UTC
LC_ALL=C
PYTHONHASHSEED=1 or 2
command: uv build --sdist --wheel --out-dir <empty-run-directory> <clean-snapshot>
```

Two independently unpacked clean snapshots are required on each side; build
outputs, caches, and egg-info from one run may not enter another snapshot.

The verified clean-base wheel is reproducible across both hash seeds:

```text
filename: projectkoios_ingestion-0.0.0-py3-none-any.whl
SHA-256: a36b04f22e29b5eae5eb33e70b0d85660419c5b7bba84d9d3d668a08f90da39b
byte size: 1256419
members: 1174
```

Both post-slice wheels must have that exact filename, digest, byte size, member
order, timestamps, compression metadata, member bytes, wheel metadata, and
RECORD rows. This proves pairwise and cross-slice wheel byte identity and zero
fixture/verifier membership.

The base sdist has 1,523 members: 1,207 regular files and 316 directories,
including exactly 28 existing top-level `tests/test__*.py` members, zero PDFs,
and zero `tests/fixtures/` members. Raw gzip and tar bytes are not reproducible
at this base because archive timestamps vary. Every raw pre/post sdist digest
and byte size must be recorded, but raw archive hash differences alone are not
a slice failure and may not be described as reproducibility.

Each of the four sdists must instead be converted to one canonical semantic
member manifest. Remove exactly the single
`projectkoios_ingestion-0.0.0/` archive-root prefix (`.` represents the root),
reject duplicate, absolute, or `..` paths, reject types other than regular file
and directory, and sort by normalized path. For every member encode a JSON
object with exactly these alphabetically sorted keys:

```text
content_sha256
gid
gname
linkname
mode
path
pax_headers
size
type
uid
uname
```

`content_sha256` is the lowercase SHA-256 for a regular file and `null` for a
directory. `type` is the one-character ASCII TarInfo type. `mode`, `uid`,
`gid`, `uname`, `gname`, `size`, and `linkname` are exact TarInfo values. Remove
only TarInfo `mtime` and PAX keys exactly `mtime`, `atime`, or `ctime`; retain all
other PAX headers, normalizing a `path` value by the same single root-prefix
rule. Encode the sorted array as UTF-8 JSON using `ensure_ascii=True`,
`sort_keys=True`, separators `(',', ':')`, and exactly one final LF.

Both clean-base builds produce the same 464,480-byte canonical manifest with:

```text
SHA-256: 98ad60e4c1ac385c66111a4a4b72b68e92ff2d14fbcce4e4137da5a3ea14c0bc
members: 1523
regular files: 1207
directories: 316
top-level tests/test__*.py members: 28
PDF members: 0
tests/fixtures/ members: 0
```

Each post-slice sdist must independently produce exactly that canonical byte
sequence and digest. Therefore neither the nested verifier, real fixtures,
request, private path, nor any changed member/content/non-time metadata may
enter the sdist. A normalized disagreement stops the slice. Raw sdist archive
reproducibility is a pre-existing limitation to revisit before any public sdist
release; this admission slice may not fix packaging or authorize release.

## Source, artifact, and offline gates

A future implementation must run and record:

- exact branch/base/request binding before worktree creation and every edit,
  copy, build, and final evidence step;
- exact `1M/5A`, no-delete/no-rename inventory and 2,387 frozen base paths,
  including no nested-test `__init__.py`;
- source and target manifest/PDF hashes, sizes, regular-file status, and `cmp`;
- exact `.gitattributes` behavior through `git check-attr` for both PDFs and
  both text files;
- canonical manifest JSON round-trip bytes with duplicate-key rejection;
- six focused fixture tests;
- full `1507 passed, 2 skipped` suite;
- unchanged 27-test benchmark gate;
- Ruff format/check and `git diff --check`;
- clean 15-file and 21-file strict scopes plus the new strict test check and
  exact 37-file union;
- exactly one scoped PyMuPDF ignore and unchanged broader two-error typing
  baseline;
- the exact two-pre/two-post wheel and sdist build matrix above;
- exact reproducible pre/post wheel bytes and the exact canonical pre/post sdist
  semantic manifests above;
- independent inspection of both post wheels and both post sdists proving zero
  fixture, nested verifier, request, or private staging member;
- no-index/no-deps fresh wheel installation and `pip check` where supported;
- AST/static proof of zero downloader/network/cross-repository import edge; and
- zero runtime network access, URL resolution, PDF mutation, extraction,
  transcript composition, publication, Workflow action, or external effect.

## Security and untrusted-document boundary

The PDFs are third-party untrusted documents even though their identities and
licenses are reviewed. Admission does not make embedded content trusted code.

The future verifier may open the exact local bytes with locked PyMuPDF only for
bounded structural facts. It must not follow links, execute JavaScript, launch
attachments, resolve external resources, submit forms, render through a browser,
or invoke embedded actions. It must assert that neither file is encrypted and
that neither contains embedded file attachments. Any structural mismatch stops
admission.

The fixtures may not be supplied to a model, external service, remote scanner,
or publication pipeline in this slice. Later processing requires its own exact
request and authorization.

## Explicitly excluded future work

The fixture-admission slice may not:

- add any third PDF;
- use a synthetic PDF in place of either exact selected article;
- edit the existing synthetic fixture matrix, generator, README, or manifest;
- create expected transcript, extraction, OCR, equation, table, figure,
  reference, claim, or scientific outputs;
- execute `koios-ingest-pdf`, either transcript-batch CLI, a Workflow, child
  Workflow, registry, scheduler, worker, retry, persistence, or publication;
- add a Workflow SDK dependency or import;
- edit production Python, project metadata, dependency locks, CPN definitions,
  workflow definitions, or owner adapters;
- promote a References identity/citekey or alter a References repository;
- infer scientific correctness, relevance, citation support, extraction
  quality, or publication acceptance;
- use a cross-repository path at test/build/runtime after the one-time copy;
- fetch, repair, rewrite, normalize, recompress, linearize, decrypt, sign, or
  otherwise change the PDFs;
- add Git LFS, filters, remote object storage, or network-backed fixtures;
- stage, checkpoint, commit, push, merge, tag, publish, release, or deploy
  without separate exact authorization; or
- modify any path outside the exact future `1M/5A` inventory.

## Effect and reversibility

The current request creates only one untracked documentation file in an
isolated request worktree. It copies no article and creates no runtime or remote
effect.

A future authorized admission slice would add 6,388,714 exact third-party PDF
bytes plus three small owned text/source files and modify `.gitattributes`. A
local checkpoint would create persistent Git objects containing redistributable
article bytes. That is a materially larger and more durable effect than an
ordinary test edit, even before push.

Before any remote publication, the source-tree change is mechanically
reversible by removing all five additions and restoring `.gitattributes` to
base `df29924c72722fbd2eaef524ba8415cdb31c894f`. Git object removal, rollback,
history rewrite, artifact deletion, or remote removal is not implied and would
require separate authorization. License/attribution duties survive any use or
redistribution that has already occurred.

## Stop conditions

Stop and return to review rather than improvising if:

- the accepted external request digest is absent or differs;
- the base, branch, tracked-path count, inventory, or frozen-path count differs;
- the private source manifest or either source PDF differs by one byte;
- References withdraws or qualifies its source/license evidence;
- Ingestion ownership or redistribution authorization is not explicit;
- exact citation, copyright, source, version, license, attribution, page, or
  rendition provenance cannot be represented truthfully;
- either future content-addressed PDF target already exists;
- copy or `cmp` changes bytes;
- either PDF is encrypted, has embedded attachments, or fails bounded parsing;
- a test requires network, private staging, another repository, generated code,
  scientific output, or a third PDF;
- the six-test, full-suite, benchmark, strict typing, baseline diagnostics,
  attribute, wheel-byte-equality, or canonical-sdist-semantic gates differ;
- any production/dependency/Workflow/References path would need to change; or
- staging, commit, push, release, processing, or runtime action would be needed
  without its own exact authorization.

A stop-condition resolution requires amended request bytes, renewed Ingestion
and References review, and a new operator-supplied accepted digest.

## Review request

Ingestion and References are asked to review this one documentation artifact
only, bound to its eventual exact SHA-256.

Ingestion should assess:

- whether it is the correct fixture and verification owner;
- whether exact `1M/5A` isolation protects the synthetic matrix and production
  ingestion behavior;
- whether the manifest/test requirements are hermetic, bounded, and usable for
  a later two-item per-PDF pilot; and
- whether the admission slice avoids claiming processing or Workflow outcomes.

References should assess:

- exact article/DOI/rendition/source/version/copyright/license/attribution facts;
- the source-evidence manifest and `unaccepted-candidate` boundary;
- redistribution and third-party-material caveats;
- whether content-addressed filenames avoid identity promotion; and
- whether any additional provenance is required before exact-byte admission.

Both should challenge the external digest protocol, exact binary effect,
security boundary, copy protocol, manifest shape, test allocation, baseline
counts, wheel and semantic-sdist invariance, stop conditions, and explicit
exclusions.

For every finding, use exactly one canonical disposition:

```text
FindingDisposition: MUST_FIX | HUMAN_DECISION_REQUIRED | SAFE_TO_DEFER | NO_ACTION_REQUIRED
Problem: ...
Evidence: ...
Consequence: ...
Next action: ...
```

Then report exactly one technical outcome and one independent operator request:

```text
ReviewOutcome: CHANGES_REQUIRED | REVIEW_INCONCLUSIVE | NO_BLOCKING_FINDINGS
OperatorRequest: NONE | CLARIFICATION_REQUIRED | DECISION_REQUIRED | AUTHORIZATION_REQUIRED | OUTCOME_CONFIRMATION_REQUIRED
```

Request review acceptance authorizes no fixture selection, copy, edit,
implementation, staging, checkpoint, commit, push, merge, identity promotion,
scientific use, Workflow adoption, processing, publication, release, or
deployment. Every protected next step requires separate exact operator
authorization.
