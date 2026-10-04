from __future__ import annotations


class TranscriptionLimitError(ValueError):
    """Raised before transcription composition exceeds a hard bound."""
