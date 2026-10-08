"""Reference claim-candidate failures."""


class ReferenceClaimCandidateError(ValueError):
    """Base failure for a bounded reference claim candidate."""


class ReferenceClaimCandidateVerificationError(ReferenceClaimCandidateError):
    """Raised when projection inputs do not form one exact evidence lineage."""
