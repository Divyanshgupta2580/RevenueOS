"""Structured domain exceptions for Razorpay integration."""

from apps.core.exceptions import RevenueOSError


class RazorpayError(RevenueOSError):
    """Base exception for all Razorpay adapter operations."""
    def __init__(self, message: str, code: str = "RAZORPAY_ERROR") -> None:
        super().__init__(message, code=code)


class RazorpayAuthError(RazorpayError):
    """Raised when Razorpay credentials are invalid or rejected (HTTP 401)."""
    def __init__(self, message: str = "Razorpay authentication failed.") -> None:
        super().__init__(message, code="RAZORPAY_AUTH_ERROR")


class RazorpayApiError(RazorpayError):
    """Raised when Razorpay API returns a 4xx or 5xx error payload."""
    def __init__(self, message: str, status_code: int = 400, details: dict | None = None) -> None:
        super().__init__(message, code="RAZORPAY_API_ERROR")
        self.status_code = status_code
        self.details = details or {}


class RazorpayNetworkError(RazorpayError):
    """Raised when connection to Razorpay times out or network drops."""
    def __init__(self, message: str = "Network connection to Razorpay failed.") -> None:
        super().__init__(message, code="RAZORPAY_NETWORK_ERROR")
