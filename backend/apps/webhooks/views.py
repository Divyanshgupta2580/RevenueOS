"""HTTP Webhook View for Inbound Razorpay Notifications."""

import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.webhooks.processor import WebhookEventProcessor
from apps.webhooks.verifier import verify_razorpay_signature

logger = logging.getLogger("revenueos.webhooks")


@csrf_exempt
@require_POST
def razorpay_webhook_view(request: HttpRequest) -> JsonResponse:
    """Secure endpoint for receiving, authenticating, and processing Razorpay webhooks."""
    raw_body = request.body
    signature = request.headers.get("X-Razorpay-Signature") or request.META.get("HTTP_X_RAZORPAY_SIGNATURE")

    # 1. Cryptographic Signature Verification
    if not verify_razorpay_signature(raw_body, signature):
        logger.warning("Rejected webhook with invalid or missing HMAC signature.")
        return JsonResponse(
            {"error": "INVALID_SIGNATURE", "message": "HMAC signature verification failed."},
            status=400,
        )

    # 2. Parse JSON Payload
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Rejected malformed webhook with invalid JSON payload.")
        return JsonResponse(
            {"error": "MALFORMED_PAYLOAD", "message": "Request body must be valid JSON."},
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"error": "MALFORMED_PAYLOAD", "message": "Payload must be a JSON object."},
            status=400,
        )

    # 3. Idempotent Processing and State Sync
    outcome = WebhookEventProcessor.process_event(payload)

    return JsonResponse({"status": "ok", "outcome": outcome}, status=200)
