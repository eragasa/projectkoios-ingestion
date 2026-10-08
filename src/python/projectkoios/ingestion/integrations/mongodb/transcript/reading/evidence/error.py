"""Typed MongoDB reading-evidence adapter failures."""


class MongoReadingEvidenceError(RuntimeError):
    """Describe one provider failure without leaking vendor values."""

    __slots__ = ("code",)

    def __init__(self, *, code: str, message: str) -> None:
        if type(code) is not str or not code:
            raise ValueError("provider error code must be non-empty")
        if type(message) is not str or not message:
            raise ValueError("provider error message must be non-empty")
        if len(code.encode("utf-8", errors="strict")) > 128:
            raise ValueError("provider error code exceeds its limit")
        if len(message.encode("utf-8", errors="strict")) > 2_048:
            raise ValueError("provider error message exceeds its limit")
        self.code = code
        super().__init__(message)
