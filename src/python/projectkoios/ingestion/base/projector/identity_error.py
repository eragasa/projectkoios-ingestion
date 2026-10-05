"""Identity-specific projector failures."""

from projectkoios.ingestion.base.projector.error import ProjectionContractError


class ProjectionIdentityError(ProjectionContractError):
    """Report inconsistent or duplicate identities during projection.

    Notes
    -----
    This error is narrower than ``ProjectionContractError``. It indicates
    that values satisfy the expected structural contract but disagree about
    which evidence, projector, schema, or projected object they identify.
    Callers may therefore distinguish identity ambiguity from malformed input
    without treating either condition as retryable.
    """
