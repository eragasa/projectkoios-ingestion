"""Sphinx configuration for ProjectKoios Ingestion API documentation."""

from __future__ import annotations

import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPOSITORY_ROOT / "src" / "python"))

project = "ProjectKoios Ingestion"
author = "ProjectKoios"
copyright = "2026, ProjectKoios"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

root_doc = "index"
exclude_patterns = ["_build"]

# NumPy-style docstrings are the only enabled Napoleon dialect. Keeping Google
# parsing disabled prevents the same headings from receiving two meanings.
napoleon_numpy_docstring = True
napoleon_google_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_use_param = True
napoleon_use_rtype = True

# Public classes and methods remain visible in source order. Undocumented
# private implementation details are intentionally excluded from API pages.
autodoc_member_order = "bysource"
autodoc_typehints = "signature"
autodoc_default_options = {
    "members": True,
}

# External base classes and third-party adapter types are intentionally outside
# this repository's inventory, so strict cross-project reference checking is
# disabled. ``sphinx-build -W`` still fails on ordinary documentation warnings.
nitpicky = False
html_theme = "alabaster"
