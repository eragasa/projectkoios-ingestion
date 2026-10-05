"""Workflow-facing disposition for one extraction action outcome."""

from __future__ import annotations

from enum import StrEnum


class ExtractionActionDisposition(StrEnum):
    """Whether Workflow may continue, retry identically, or must stop."""

    CONTINUE = "continue"
    RETRY_SAME_REQUEST = "retry_same_request"
    AUTHORITY_REQUIRED = "authority_required"
    STOP_INVALID_EVIDENCE = "stop_invalid_evidence"
    STOP_AMBIGUOUS_EVIDENCE = "stop_ambiguous_evidence"
