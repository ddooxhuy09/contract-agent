class DomainError(Exception):
    """Base domain error."""


class NotFoundError(DomainError):
    pass


class AuthError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class AnalysisFailedError(DomainError):
    """The analysis could not be produced (e.g. no clauses could be extracted)."""
