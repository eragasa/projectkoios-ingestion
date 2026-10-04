"""Shared repository-local test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def repository_root() -> Path:
    """Return the repository root without per-test parent traversal."""
    return Path(__file__).parent.parent


@pytest.fixture
def pdf_fixture_directory() -> Path:
    """Return the maintained PDF-fixture directory."""
    return Path(__file__).parent / "fixtures" / "pdf"
