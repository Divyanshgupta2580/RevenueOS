"""Dedicated Razorpay REST API adapter for Test Mode operations.

Encapsulates all external HTTP calls to Razorpay. Strictly prohibits logging
of credentials, secrets, or raw authentication tokens.
"""

import logging
from typing import Any

import requests
from django.conf import settings
from requests.auth import HTTPBasicAuth

from apps.core.money import validate_minor_units
from apps.razorpay_adapter.exceptions import (
    RazorpayApiError,
    RazorpayAuthError,
    RazorpayError,
    RazorpayNetworkError,
)

logger = logging.getLogger("revenueos.razorpay")


class RazorpayAdapter:
    """Isolated client for Razorpay Test Mode REST endpoints."""

    BASE_URL = "https://api.razorpay.com/v1"
    TIMEOUT_SECONDS = 6.0

    def __init__(
        self,
        key_id: str | None = None,
        key_secret: str | None = None,
        session: requests.Session | None = None,
        simulate_if_unconfigured: bool = True,
    ) -> None:
        self.key_id = key_id if key_id is not None else getattr(settings, "RAZORPAY_KEY_ID", "")
        self.key_secret = key_secret if key_secret is not None else getattr(settings, "RAZORPAY_KEY_SECRET", "")
        self._session = session or requests.Session()
        self.simulate_if_unconfigured = simulate_if_unconfigured

    def _get_auth(self) -> HTTPBasicAuth:
        if not self.key_id or not self.key_secret:
            raise RazorpayAuthError("Razorpay credentials (KEY_ID / KEY_SECRET) are not configured.")
        return HTTPBasicAuth(self.key_id, self.key_secret)

    def is_configured(self) -> bool:
        return bool(self.key_id and self.key_secret)

    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute request with strict error translation and sanitized logging."""
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        auth = self._get_auth()

        # Sanitize log (no secrets, no customer card numbers)
        logger.info(f"Razorpay API request: {method} {endpoint}")

        try:
            response = self._session.request(
                method=method,
                url=url,
                auth=auth,
                json=json_data,
                params=params,
                timeout=self.TIMEOUT_SECONDS,
                headers={"User-Agent": "RevenueOS-DecisionEngine/1.0"},
            )
        except requests.Timeout as exc:
            logger.warning(f"Razorpay request timed out: {method} {endpoint}")
            raise RazorpayNetworkError(f"Connection to Razorpay timed out ({self.TIMEOUT_SECONDS}s).") from exc
        except requests.RequestException as exc:
            logger.error(f"Razorpay network connection error: {exc}")
            raise RazorpayNetworkError("Network error while connecting to Razorpay.") from exc

        # Handle HTTP status codes
        if response.status_code == 401:
            logger.error("Razorpay returned HTTP 401 Unauthorized.")
            raise RazorpayAuthError("Invalid Razorpay API credentials.")

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        if not response.ok:
            error_data = data.get("error", {}) if isinstance(data, dict) else {}
            err_desc = error_data.get("description") or response.text or "Razorpay API error"
            logger.warning(f"Razorpay API error ({response.status_code}): {err_desc}")
            raise RazorpayApiError(
                message=f"Razorpay API Error: {err_desc}",
                status_code=response.status_code,
                details=error_data,
            )

        if not isinstance(data, dict):
            raise RazorpayError("Unexpected non-JSON response from Razorpay.")

        return data

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        """Fetch payment details from Razorpay."""
        if not payment_id:
            raise RazorpayError("payment_id is required.")
        if not self.is_configured():
            if self.simulate_if_unconfigured:
                return {"id": payment_id, "status": "failed", "simulated": True}
            raise RazorpayAuthError("Razorpay credentials (KEY_ID / KEY_SECRET) are not configured.")
        return self._request("GET", f"payments/{payment_id}")

    def create_payment_link(
        self,
        amount_paise: int,
        currency: str = "INR",
        customer_email: str | None = None,
        customer_contact: str | None = None,
        description: str = "RevenueOS Recovery Payment Link",
        reference_id: str | None = None,
    ) -> dict[str, Any]:
        """Create standard payment link with integer paise amount."""
        validated_amount = validate_minor_units(amount_paise)

        if not self.is_configured():
            if self.simulate_if_unconfigured:
                import uuid
                plink_id = f"plink_{uuid.uuid4().hex[:12]}"
                return {
                    "id": plink_id,
                    "amount": validated_amount,
                    "currency": currency,
                    "status": "created",
                    "short_url": f"https://rzp.io/i/{plink_id}",
                    "simulated": True,
                }
            raise RazorpayAuthError("Razorpay credentials (KEY_ID / KEY_SECRET) are not configured.")

        payload: dict[str, Any] = {
            "amount": validated_amount,
            "currency": currency,
            "accept_partial": False,
            "description": description,
            "notify": {
                "sms": bool(customer_contact),
                "email": bool(customer_email),
            },
            "reminder_enable": True,
        }

        if reference_id:
            payload["reference_id"] = reference_id

        customer: dict[str, str] = {}
        if customer_email:
            customer["email"] = customer_email
        if customer_contact:
            customer["contact"] = customer_contact
        if customer:
            payload["customer"] = customer

        return self._request("POST", "payment_links", json_data=payload)

    def notify_payment_link(self, link_id: str, medium: str = "sms") -> dict[str, Any]:
        """Send recovery nudge/reminder notification for an existing payment link."""
        if not link_id:
            raise RazorpayError("link_id is required.")
        if not self.is_configured():
            if self.simulate_if_unconfigured:
                return {"success": True, "simulated": True}
            raise RazorpayAuthError("Razorpay credentials (KEY_ID / KEY_SECRET) are not configured.")

        norm_medium = medium.lower().strip()
        if norm_medium not in ["sms", "email"]:
            norm_medium = "sms"
        return self._request("POST", f"payment_links/{link_id}/notify_by/{norm_medium}")
