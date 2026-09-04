# ruff: noqa: E402, I001
import os
import sys

import django

sys.path.insert(0, "backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "revenueos.settings")
django.setup()

from apps.database.client import get_database
from apps.authentication.services import create_session

db = get_database()
user = db["users"].find_one({"username": "operator@revenueos.local"})
if not user:
    # Fallback to any operator
    user = db["users"].find_one({"role": "operator"})

if not user:
    from apps.authentication.services import create_user
    user = create_user("operator@revenueos.local", "OperatorPass123!", role="operator")

token = create_session(
    user_id=user.get("_id") or "op_live_01",
    username=user.get("username", "operator@revenueos.local"),
    role="operator",
)

print(f"SESSION_TOKEN={token}")
