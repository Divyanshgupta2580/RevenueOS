"""Safely inspect MongoDB Atlas for user and payment records without leaking secrets."""

import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "revenueos.settings")

import django  # noqa: E402

django.setup()

from apps.database.client import get_database  # noqa: E402


def inspect_user(email: str):
    db = get_database()
    user = db["users"].find_one({"username": email.lower().strip()})
    if not user:
        return {"found": False}

    has_plaintext = False
    for k, v in user.items():
        if k != "password_hash" and isinstance(v, str) and ("RevOS" in v or "SecPass" in v):
            has_plaintext = True

    password_hash = user.get("password_hash", "")
    is_argon2id = password_hash.startswith("$argon2id$")

    return {
        "found": True,
        "collection": "users",
        "username": user.get("username"),
        "role": user.get("role"),
        "has_argon2id_hash": is_argon2id,
        "hash_prefix": password_hash[:15] if is_argon2id else "INVALID",
        "has_plaintext_password": has_plaintext,
        "created_at": str(user.get("created_at")),
    }


def inspect_payments():
    db = get_database()
    payments = list(db["payments"].find().sort("created_at", -1).limit(5))
    results = []
    for p in payments:
        payment_id = str(p.get("razorpay_payment_id", ""))
        order_id = str(p.get("razorpay_order_id", ""))
        redacted_payment_id = payment_id[:6] + "..." + payment_id[-4:] if len(payment_id) > 10 else payment_id
        redacted_order_id = order_id[:6] + "..." + order_id[-4:] if len(order_id) > 10 else order_id

        results.append({
            "collection": "payments",
            "amount_paise": p.get("amount_paise"),
            "currency": p.get("currency"),
            "status": p.get("status"),
            "payment_id_redacted": redacted_payment_id,
            "order_id_redacted": redacted_order_id,
            "created_at": str(p.get("created_at")),
        })
    return results


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "inspect"
    if action == "user" and len(sys.argv) > 2:
        import json
        print(json.dumps(inspect_user(sys.argv[2]), indent=2))
    elif action == "payments":
        import json
        print(json.dumps(inspect_payments(), indent=2))
    else:
        import json
        print("USERS COUNT:", get_database()["users"].count_documents({}))
        print("PAYMENTS COUNT:", get_database()["payments"].count_documents({}))
