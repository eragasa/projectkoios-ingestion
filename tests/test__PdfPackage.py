from __future__ import annotations

import importlib.metadata
import subprocess
import sys


def test__base_package_import__does_not_import_optional_pymupdf() -> None:
    script = """
import sys
class BlockPyMuPdf:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "pymupdf" or fullname.startswith("pymupdf."):
            raise AssertionError("base import attempted to load PyMuPDF")
        return None
sys.meta_path.insert(0, BlockPyMuPdf())
import projectkoios.ingestion
assert "pymupdf" not in sys.modules
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test__missing_optional_dependency__raises_typed_error_on_use() -> None:
    script = """
import sys
class BlockPyMuPdf:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "pymupdf" or fullname.startswith("pymupdf."):
            raise ModuleNotFoundError("blocked optional dependency")
        return None
sys.meta_path.insert(0, BlockPyMuPdf())
from io import BytesIO
from projectkoios.ingestion import (
    PdfDependencyUnavailableError,
    PyMuPdfExtractor,
    SourceDocument,
)
content = b"fixture"
source = SourceDocument.from_bytes(
    content,
    source_id="fixture",
    media_type="application/pdf",
    locator="memory://fixture.pdf",
)
try:
    PyMuPdfExtractor().extract(source, BytesIO(content))
except PdfDependencyUnavailableError:
    pass
else:
    raise AssertionError("missing PyMuPDF was not reported")
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test__missing_optional_dependency__renderer_raises_typed_error() -> None:
    script = """
import sys
class BlockPyMuPdf:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "pymupdf" or fullname.startswith("pymupdf."):
            raise ModuleNotFoundError("blocked optional dependency")
        return None
sys.meta_path.insert(0, BlockPyMuPdf())
from io import BytesIO
from projectkoios.ingestion import (
    PageRegionSelection,
    PdfDependencyUnavailableError,
    PyMuPdfRegionRenderer,
    SourceDocument,
)
content = b"fixture"
source = SourceDocument.from_bytes(
    content,
    source_id="fixture",
    media_type="application/pdf",
    locator="memory://fixture.pdf",
)
selection = PageRegionSelection.for_full_page(source, 0)
try:
    PyMuPdfRegionRenderer().render(source, BytesIO(content), (selection,))
except PdfDependencyUnavailableError:
    pass
else:
    raise AssertionError("missing PyMuPDF was not reported")
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test__package_entry_point__targets_cli_and_module_help_works() -> None:
    entry_points = importlib.metadata.entry_points(
        group="console_scripts",
        name="koios-ingest-pdf",
    )
    entry_point = next(
        entry
        for entry in entry_points
        if entry.value == "projectkoios.ingestion.cli:main"
    )
    console_script = entry_point.dist.locate_file(
        f"../../../bin/{entry_point.name}"
    ).resolve()
    completed = subprocess.run(
        [str(console_script), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert console_script.is_file()
    assert completed.returncode == 0
    assert "--raw-text-directory" in completed.stdout
    assert "--cache-root" in completed.stdout
