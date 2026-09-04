"""HTTP Views for Razorpay Standard Web Checkout (Order Creation & Payment Verification)."""

import json
import logging
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.database.repositories import ActionRepository, PaymentRepository
from apps.razorpay_adapter.adapter import RazorpayAdapter
from apps.razorpay_adapter.exceptions import (
    RazorpayApiError,
    RazorpayAuthError,
    RazorpayError,
    RazorpayNetworkError,
)

logger = logging.getLogger("revenueos.razorpay")


def _cors_response(response: HttpResponse) -> HttpResponse:
    """Attach permissive CORS headers for local and cross-origin frontend clients."""
    origin = getattr(settings, "FRONTEND_ORIGIN", "*") or "*"
    response["Access-Control-Allow-Origin"] = origin if origin != "*" else "*"
    response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    response["Access-Control-Allow-Credentials"] = "true"
    return response


@csrf_exempt
def create_order_view(request: HttpRequest) -> HttpResponse:
    """Create a Razorpay Standard Checkout order.

    Accepts:
        POST: { "amount": <int paise >= 100>, "currency": "INR", "receipt": "..." }
    Returns:
        JSON: { "order_id": "...", "amount": 50000, "currency": "INR", "key_id": "..." }
    """
    if request.method == "OPTIONS":
        return _cors_response(HttpResponse(status=200))

    if request.method != "POST":
        return _cors_response(
            JsonResponse({"error": "METHOD_NOT_ALLOWED", "message": "Only POST requests are permitted."}, status=405)
        )

    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _cors_response(
            JsonResponse({"error": "MALFORMED_JSON", "message": "Request body must be valid JSON."}, status=400)
        )

    raw_amount = body.get("amount")
    if raw_amount is None:
        return _cors_response(
            JsonResponse({"error": "MISSING_AMOUNT", "message": "The 'amount' field (in paise) is required."}, status=400)
        )

    try:
        amount_paise = int(raw_amount)
    except (TypeError, ValueError):
        return _cors_response(
            JsonResponse({"error": "INVALID_AMOUNT", "message": "Amount must be an integer in minor units (paise)."}, status=400)
        )

    # Minimum amount validation: 100 paise (₹1.00)
    if amount_paise < 100:
        return _cors_response(
            JsonResponse(
                {"error": "AMOUNT_TOO_LOW", "message": f"Minimum order amount is 100 paise (got {amount_paise})."},
                status=400,
            )
        )

    currency = str(body.get("currency", "INR")).upper().strip() or "INR"
    receipt = body.get("receipt")
    notes = body.get("notes") or {}

    adapter = RazorpayAdapter()

    try:
        order = adapter.create_order(
            amount_paise=amount_paise,
            currency=currency,
            receipt=receipt,
            notes=notes,
        )
    except RazorpayAuthError as exc:
        logger.error(f"Razorpay authentication error creating order: {exc}")
        return _cors_response(
            JsonResponse({"error": "AUTH_FAILURE", "message": "Invalid Razorpay credentials."}, status=401)
        )
    except (RazorpayApiError, RazorpayNetworkError, RazorpayError) as exc:
        logger.error(f"Razorpay API error creating order: {exc}")
        return _cors_response(
            JsonResponse({"error": "RAZORPAY_API_ERROR", "message": str(exc)}, status=500)
        )
    except Exception as exc:
        logger.error(f"Unexpected error creating order: {exc}")
        return _cors_response(
            JsonResponse({"error": "INTERNAL_ERROR", "message": "Failed to create payment order."}, status=500)
        )

    order_id = order.get("order_id") or order.get("id")
    response_data: dict[str, Any] = {
        "order_id": order_id,
        "amount": order.get("amount", amount_paise),
        "currency": order.get("currency", currency),
        "status": order.get("status", "created"),
        "key_id": adapter.key_id,
    }
    if order.get("receipt"):
        response_data["receipt"] = order["receipt"]

    return _cors_response(JsonResponse(response_data, status=200))


@csrf_exempt
def verify_payment_view(request: HttpRequest) -> HttpResponse:
    """Verify HMAC-SHA256 signature for Razorpay Standard Web Checkout.

    Accepts:
        POST: {
            "razorpay_order_id": "...",
            "razorpay_payment_id": "...",
            "razorpay_signature": "..."
        }
    """
    if request.method == "OPTIONS":
        return _cors_response(HttpResponse(status=200))

    if request.method != "POST":
        return _cors_response(
            JsonResponse({"error": "METHOD_NOT_ALLOWED", "message": "Only POST requests are permitted."}, status=405)
        )

    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _cors_response(
            JsonResponse({"error": "MALFORMED_JSON", "message": "Request body must be valid JSON."}, status=400)
        )

    order_id = (
        body.get("razorpay_order_id")
        or body.get("order_id")
        or ""
    ).strip()
    payment_id = (
        body.get("razorpay_payment_id")
        or body.get("payment_id")
        or ""
    ).strip()
    signature = (
        body.get("razorpay_signature")
        or body.get("signature")
        or ""
    ).strip()

    # Verify all 3 fields are provided
    missing_fields = []
    if not order_id:
        missing_fields.append("razorpay_order_id")
    if not payment_id:
        missing_fields.append("razorpay_payment_id")
    if not signature:
        missing_fields.append("razorpay_signature")

    if missing_fields:
        return _cors_response(
            JsonResponse(
                {
                    "error": "MISSING_FIELDS",
                    "message": f"Missing required verification fields: {', '.join(missing_fields)}",
                    "missing": missing_fields,
                },
                status=400,
            )
        )

    adapter = RazorpayAdapter()

    try:
        is_valid = adapter.verify_payment_signature(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature,
        )
    except RazorpayAuthError as exc:
        logger.error(f"Razorpay authentication error during signature verification: {exc}")
        return _cors_response(
            JsonResponse({"error": "AUTH_FAILURE", "message": "Razorpay KEY_SECRET is not configured."}, status=401)
        )
    except Exception as exc:
        logger.error(f"Unexpected error verifying signature: {exc}")
        return _cors_response(
            JsonResponse({"error": "VERIFICATION_ERROR", "message": "Error occurred during verification."}, status=500)
        )

    if not is_valid:
        logger.warning(f"Payment verification failed: signature mismatch for order {order_id} / payment {payment_id}")
        return _cors_response(
            JsonResponse(
                {
                    "status": "failure",
                    "verified": False,
                    "message": "Signature verification failed. Invalid payment signature.",
                },
                status=400,
            )
        )

    logger.info(f"Payment verified successfully for order {order_id} and payment {payment_id}")

    # Mark as recovered/captured in database if matching payment exists
    associated_payment_id = body.get("payment_reference") or payment_id
    try:
        matched_payment = PaymentRepository.get_by_id(associated_payment_id)
        if matched_payment:
            PaymentRepository.update_status(
                payment_id=associated_payment_id,
                status="captured",
                recovery_status="recovered",
            )
            import uuid
            ActionRepository.create({
                "action_id": f"act_chk_{uuid.uuid4().hex[:10]}",
                "action_type": "CHECKOUT_PAYMENT_VERIFIED",
                "payment_id": associated_payment_id,
                "idempotency_key": f"idemp_chk_{order_id}_{payment_id}",
                "external_reference": payment_id,
                "status": "EXECUTED",
                "payload": {"order_id": order_id, "payment_id": payment_id},
                "result": {"verified": True},
            })
    except Exception as exc:
        logger.warning(f"Could not update payment state for {associated_payment_id}: {exc}")

    return _cors_response(
        JsonResponse(
            {
                "status": "success",
                "verified": True,
                "message": "Payment signature verified successfully.",
                "order_id": order_id,
                "payment_id": payment_id,
            },
            status=200,
        )
    )
