from app.core.exceptions import AppError, BusinessRuleError


class UnknownAIToolError(BusinessRuleError):
    pass


class InvalidAIToolArgumentsError(BusinessRuleError):
    pass


class AIToolExecutionError(AppError):
    status_code = 500


class AIProviderError(AppError):
    status_code = 503


class AIProviderTimeoutError(AppError):
    status_code = 504


class AIResponseError(AppError):
    status_code = 502
