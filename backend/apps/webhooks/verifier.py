"""Razorpay Webhook Signature Verification using HMAC-SHA256."""

import hashlib
import hmac
import logging

from django.conf import settings

logger = logging.getLogger("revenueos.webhooks")


def verify_razorpay_signature(raw_body: bytes, signature: str | None, secret: str | None = None) -> bool:
    """Verify cryptographic authenticity of inbound Razorpay webhook request.

    Uses constant-time comparison to prevent timing attacks.
    """
    if not signature:
        logger.warning("Webhook rejected: missing X-Razorpay-Signature header.")
        return False

    webhook_secret = secret or getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")
    if not webhook_secret:
        # In test mode with unconfigured webhook secret, reject in production but allow test secret if specified
        logger.warning("Webhook verification failed: RAZORPAY_WEBHOOK_SECRET not configured.")
        return False

    try:
        computed_hmac = hmac.new(
            key=webhook_secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed_hmac, signature.strip())
    except Exception as exc:
        logger.error(f"Error computing webhook signature HMAC: {exc}")
        return False
