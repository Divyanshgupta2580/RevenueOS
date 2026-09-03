"""Core exception hierarchy for RevenueOS."""


class RevenueOSError(Exception):
    """Base exception for all domain errors in RevenueOS."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class AuthenticationError(RevenueOSError):
    """Raised when authentication fails."""
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, code="UNAUTHORIZED")


class PolicyViolationError(RevenueOSError):
    """Raised when an action violates the Guarded Autopilot policy."""
    def __init__(self, message: str, code: str = "POLICY_VIOLATION") -> None:
        super().__init__(message, code=code)


class IdempotencyError(RevenueOSError):
    """Raised when duplicate execution is attempted."""
    def __init__(self, message: str = "Duplicate action detected") -> None:
        super().__init__(message, code="DUPLICATE_ACTION")


class RazorpayAdapterError(RevenueOSError):
    """Raised when external Razorpay communication fails."""
    def __init__(self, message: str, code: str = "RAZORPAY_ERROR") -> None:
        super().__init__(message, code=code)
