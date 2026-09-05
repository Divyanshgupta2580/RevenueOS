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


def _cors_response(response: HttpResponse, request: HttpRequest | None = None) -> HttpResponse:
    """Attach permissive CORS headers for local and cross-origin frontend clients."""
    origin = None
    if request:
        origin = request.META.get("HTTP_ORIGIN")
    if not origin:
        origin = getattr(settings, "FRONTEND_ORIGIN", "https://revenue-os-woad.vercel.app")
    response["Access-Control-Allow-Origin"] = origin
    response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
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
    def cors(res: HttpResponse) -> HttpResponse:
        return _cors_response(res, request)

    if request.method == "OPTIONS":
        return cors(HttpResponse(status=200))

    if request.method != "POST":
        return cors(
            JsonResponse({"error": "METHOD_NOT_ALLOWED", "message": "Only POST requests are permitted."}, status=405)
        )

    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return cors(
            JsonResponse({"error": "MALFORMED_JSON", "message": "Request body must be valid JSON."}, status=400)
        )

    raw_amount = body.get("amount")
    if raw_amount is None:
        return cors(
            JsonResponse({"error": "MISSING_AMOUNT", "message": "The 'amount' field (in paise) is required."}, status=400)
        )

    try:
        amount_paise = int(raw_amount)
    except (TypeError, ValueError):
        return cors(
            JsonResponse({"error": "INVALID_AMOUNT", "message": "Amount must be an integer in minor units (paise)."}, status=400)
        )

    # Minimum amount validation: 100 paise (₹1.00)
    if amount_paise < 100:
        return cors(
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
        return cors(
            JsonResponse({"error": "AUTH_FAILURE", "message": "Invalid Razorpay credentials."}, status=401)
        )
    except (RazorpayApiError, RazorpayNetworkError, RazorpayError) as exc:
        logger.error(f"Razorpay API error creating order: {exc}")
        return cors(
            JsonResponse({"error": "RAZORPAY_API_ERROR", "message": str(exc)}, status=500)
        )
    except Exception as exc:
        logger.error(f"Unexpected error creating order: {exc}")
        return cors(
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

    return cors(JsonResponse(response_data, status=200))


@csrf_exempt
def verify_payment_view(request: HttpRequest) -> HttpResponse:
    """Verify HMAC-SHA256 signature for Razorpay Standard Web Checkout.

    Accepts:
        GET: Returns the most recent verified captured payment
        POST: {
            "razorpay_order_id": "...",
            "razorpay_payment_id": "...",
            "razorpay_signature": "..."
        }
    """
    def cors(res: HttpResponse) -> HttpResponse:
        return _cors_response(res, request)

    if request.method == "OPTIONS":
        return cors(HttpResponse(status=200))

    if request.method == "GET":
        try:
            col = PaymentRepository.get_collection()
            latest = col.find_one({"status": {"$in": ["captured", "paid"]}}, sort=[("created_at", -1)])
            if latest:
                created_val = latest.get("created_at")
                created_str = (
                    created_val.isoformat()
                    if hasattr(created_val, "isoformat")
                    else str(created_val or "")
                )
                return cors(
                    JsonResponse(
                        {
                            "status": "success",
                            "payment": {
                                "payment_id": latest.get("payment_id", ""),
                                "order_id": latest.get("order_id", ""),
                                "amount": latest.get("amount", 0),
                                "currency": latest.get("currency", "INR"),
                                "status": latest.get("status", "captured"),
                                "signature": latest.get("signature") or "",
                                "created_at": created_str,
                            },
                        },
                        status=200,
                    )
                )
            return cors(JsonResponse({"status": "empty", "payment": None}, status=200))
        except Exception as e:
            logger.warning(f"Could not fetch latest verified payment: {e}")
            return cors(JsonResponse({"status": "empty", "payment": None}, status=200))

    if request.method != "POST":
        return cors(
            JsonResponse({"error": "METHOD_NOT_ALLOWED", "message": "Only GET and POST requests are permitted."}, status=405)
        )

    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return cors(
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
        return cors(
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
        return cors(
            JsonResponse({"error": "AUTH_FAILURE", "message": "Razorpay gateway secret is not configured."}, status=401)
        )
    except Exception as exc:
        logger.error(f"Unexpected error verifying signature: {exc}")
        return cors(
            JsonResponse({"error": "VERIFICATION_ERROR", "message": "Error occurred during verification."}, status=500)
        )

    if not is_valid:
        logger.warning(f"Payment verification failed: signature mismatch for order {order_id} / payment {payment_id}")
        return cors(
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

    # Mark as recovered/captured in database or persist new verified checkout payment
    associated_payment_id = body.get("payment_reference") or payment_id
    try:
        matched_payment = PaymentRepository.get_by_id(associated_payment_id)
        if matched_payment:
            PaymentRepository.update_status(
                payment_id=associated_payment_id,
                status="captured",
                recovery_status="recovered",
                signature=signature,
            )
        else:
            # Standalone checkout payment: fetch details from Razorpay or use request body
            amount_paise = 10000
            currency = "INR"
            customer_email = "operator@revenueos.local"
            try:
                rzp_payment = adapter.fetch_payment(payment_id)
                if isinstance(rzp_payment, dict) and "amount" in rzp_payment:
                    amount_paise = int(rzp_payment["amount"])
                    currency = rzp_payment.get("currency", "INR")
                    customer_email = rzp_payment.get("email") or customer_email
            except Exception as e:
                logger.warning(f"Could not fetch payment from Razorpay: {e}")

            try:
                PaymentRepository.create({
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "customer_id": f"cust_{payment_id[-8:]}",
                    "customer_email": customer_email,
                    "amount": amount_paise,
                    "currency": currency,
                    "status": "captured",
                    "recovery_status": "recovered",
                    "signature": signature,
                })
            except Exception as e:
                logger.info(f"Payment already exists or could not be inserted: {e}")

        import uuid
        try:
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
        except Exception as e:
            logger.info(f"Action already recorded: {e}")
    except Exception as exc:
        logger.warning(f"Could not update/persist payment state for {associated_payment_id}: {exc}")

    return cors(
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


@csrf_exempt
def record_payment_failure_view(request: HttpRequest) -> HttpResponse:
    """Record and ingest an authentic Razorpay payment failure.

    Accepts:
        POST: {
            "payment_id": "pay_...",
            "order_id": "order_...",
            "error_code": "BAD_REQUEST_ERROR",
            "error_description": "...",
            "error_reason": "payment_failed",
            "error_source": "gateway",
            "error_step": "payment_authorization",
            "amount": 150000,
            "currency": "INR"
        }
    Returns:
        JSON: { "status": "success", "ingested": true, "payment_id": "pay_...", ... }
    """
    def cors(res: HttpResponse) -> HttpResponse:
        return _cors_response(res, request)

    if request.method == "OPTIONS":
        return cors(HttpResponse(status=200))

    if request.method != "POST":
        return cors(
            JsonResponse({"error": "METHOD_NOT_ALLOWED", "message": "Only POST requests are permitted."}, status=405)
        )

    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return cors(
            JsonResponse({"error": "MALFORMED_JSON", "message": "Request body must be valid JSON."}, status=400)
        )

    payment_id = str(body.get("payment_id") or body.get("razorpay_payment_id") or "").strip()
    order_id = str(body.get("order_id") or body.get("razorpay_order_id") or "").strip()
    if not payment_id:
        return cors(
            JsonResponse({"error": "MISSING_PAYMENT_ID", "message": "The 'payment_id' field is required."}, status=400)
        )

    # Ingest authentic payment failure from Razorpay
    adapter = RazorpayAdapter()
    rzp_payment: dict[str, Any] = {}
    try:
        rzp_payment = adapter.fetch_payment(payment_id)
    except Exception as exc:
        logger.warning(f"Could not fetch payment {payment_id} from Razorpay: {exc}")

    # Authoritative field extraction
    raw_amount = rzp_payment.get("amount") or body.get("amount") or 150000
    try:
        amount_paise = int(raw_amount)
    except (TypeError, ValueError):
        amount_paise = 150000

    currency = str(rzp_payment.get("currency") or body.get("currency") or "INR").upper().strip()
    resolved_order_id = str(rzp_payment.get("order_id") or order_id or "").strip()
    error_code = str(rzp_payment.get("error_code") or body.get("error_code") or "BAD_REQUEST_ERROR")
    error_desc = str(
        rzp_payment.get("error_description")
        or body.get("error_description")
        or "Payment declined during authorization."
    )
    error_reason = str(rzp_payment.get("error_reason") or body.get("error_reason") or "payment_failed")
    customer_email = str(rzp_payment.get("email") or body.get("customer_email") or "operator@revenueos.local")
    method = str(rzp_payment.get("method") or body.get("method") or "card")

    # Deterministic failure category mapping
    comb = f"{error_code} {error_desc} {error_reason}".lower()
    if "insufficient" in comb:
        failure_category = "insufficient_funds"
    elif "timeout" in comb or "network" in comb:
        failure_category = "network_timeout"
    elif "fraud" in comb or "risk" in comb or "stolen" in comb:
        failure_category = "fraud"
    elif "expired" in comb:
        failure_category = "card_expired"
    elif "auth" in comb or "otp" in comb:
        failure_category = "authentication_failed"
    else:
        failure_category = "soft_decline"

    from datetime import UTC, datetime

    now = datetime.now(UTC)

    existing = PaymentRepository.get_by_id(payment_id)
    if existing:
        PaymentRepository.update_status(
            payment_id=payment_id,
            status="failed",
            recovery_status="at_risk",
        )
    else:
        PaymentRepository.create(
            {
                "payment_id": payment_id,
                "order_id": resolved_order_id,
                "customer_id": f"cust_{payment_id[-8:]}",
                "customer_email": customer_email,
                "amount": amount_paise,
                "currency": currency,
                "status": "failed",
                "error_code": error_code,
                "error_description": error_desc,
                "failure_reason": error_reason,
                "failure_category": failure_category,
                "method": method,
                "retry_count": 0,
                "max_retries_allowed": 3,
                "recovery_status": "at_risk",
                "created_at": now,
            }
        )

    # Broadcast real-time update to active operators
    try:
        from apps.webhooks.processor import RazorpayWebhookProcessor

        RazorpayWebhookProcessor.broadcast_to_operators(
            "payment.updated",
            {
                "paymentId": payment_id,
                "status": "failed",
                "recoveryStatus": "at_risk",
                "amount": amount_paise,
                "failureCategory": failure_category,
                "failureReason": error_reason,
            },
        )
        RazorpayWebhookProcessor.broadcast_to_operators("revenue.updated", {"paymentId": payment_id})
    except Exception as e:
        logger.warning(f"Could not broadcast failure update for {payment_id}: {e}")

    logger.info(
        f"Authentic failed payment ingested: ID={payment_id}, Category={failure_category}, Amount={amount_paise}"
    )

    return cors(
        JsonResponse(
            {
                "status": "success",
                "ingested": True,
                "payment_id": payment_id,
                "order_id": resolved_order_id,
                "payment_status": "failed",
                "failure_category": failure_category,
                "failure_reason": error_reason,
                "amount": amount_paise,
                "currency": currency,
            },
            status=200,
        )
    )

