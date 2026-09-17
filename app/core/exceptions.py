from typing import Any


class AppError(Exception):
    status_code = 500

    def __init__(self, message: str, errors: list[Any] | None = None) -> None:
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404


class BusinessRuleError(AppError):
    status_code = 422


class AuthenticationError(AppError):
    status_code = 401


class AuthorizationError(AppError):
    status_code = 403
