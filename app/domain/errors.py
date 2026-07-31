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
