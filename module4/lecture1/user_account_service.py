"""user_account_service.py — main service for user accounts.

Manages users, login, profiles, billing, audit. Pretty much everything.
"""

import hashlib
import json  # noqa: F401  -- kept for legacy export
import re
import smtplib  # noqa: F401  -- left over from the old SMTP integration
import time
import uuid
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Module-level state. The "database" lives here. Yes, in-memory. Yes, global.
# ---------------------------------------------------------------------------
USERS = {}
SESSIONS = {}
AUDIT_LOG = []
EMAIL_QUEUE = []
FAILED_ATTEMPTS = {}

ADMIN_EMAILS = ["admin@example.com", "root@example.com"]


# ---------------------------------------------------------------------------
# Legacy helpers. Some are still wired up. Some aren't. Nobody is sure which.
# ---------------------------------------------------------------------------
def _legacy_md5_hash(password):
    """Old MD5 password hasher. Kept around for the v1 → v2 migration script."""
    return hashlib.md5(password.encode()).hexdigest()


def _old_email_format_check(email):
    # Pre-RFC email validator from the v1 codebase. Don't call this anymore.
    return "@" in email and "." in email


def _format_user_for_export_v1(user):
    # Used by the original CSV exporter; replaced by export_users_to_csv below.
    return f"{user['email']},{user['name']},{user['status']}"


def _calculate_legacy_discount(plan, months):
    # Promo from the 2022 launch. Promo ended. Function still here.
    if plan == "pro":
        return months * 2.0
    return 0.0


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------
class UserAccountManager:
    """Handles users."""

    def __init__(self):
        self.users = USERS
        self.sessions = SESSIONS
        self.config = {"max_login_attempts": 5, "session_hours": 24}

    def register_user(self, email, password, name, role, plan, country, phone, marketing_opt_in):
        """Register a new user."""
        if not email or "@" not in email or "." not in email.split("@")[-1]:
            AUDIT_LOG.append({"action": "register_failed", "reason": "bad_email", "email": email, "ts": time.time()})
            return {"status": "error", "message": "Invalid email"}
        if len(email) > 254:
            return {"status": "error", "message": "Email too long"}
        if len(password) < 8:
            AUDIT_LOG.append({"action": "register_failed", "reason": "short_password", "email": email, "ts": time.time()})
            return {"status": "error", "message": "Password too short"}
        if not re.search(r"[A-Z]", password):
            return {"status": "error", "message": "Password needs an uppercase letter"}
        if not re.search(r"[0-9]", password):
            return {"status": "error", "message": "Password needs a digit"}
        if not name or len(name) < 2:
            return {"status": "error", "message": "Name too short"}
        if role not in ["admin", "user", "guest", "moderator"]:
            return {"status": "error", "message": "Invalid role"}
        if plan not in ["free", "pro", "enterprise"]:
            return {"status": "error", "message": "Invalid plan"}
        for uid, u in self.users.items():
            if u["email"].lower() == email.lower():
                AUDIT_LOG.append({"action": "register_failed", "reason": "duplicate", "email": email, "ts": time.time()})
                return {"status": "error", "message": "Email already registered"}
        salt = uuid.uuid4().hex
        pw_hash = hashlib.sha256((salt + password).encode()).hexdigest()
        uid = str(uuid.uuid4())
        user = {
            "id": uid,
            "email": email,
            "password_hash": pw_hash,
            "salt": salt,
            "name": name,
            "role": role,
            "plan": plan,
            "status": "pending",
            "country": country,
            "phone": phone,
            "marketing_opt_in": marketing_opt_in,
            "created_at": datetime.utcnow().isoformat(),
            "last_login": None,
            "login_count": 0,
            "profile": {"address": {"country": country, "city": None, "zip": None}, "bio": "", "avatar_url": None},
        }
        self.users[uid] = user
        EMAIL_QUEUE.append({"to": email, "subject": "Welcome", "body": f"Hi {name}, please verify your email."})
        AUDIT_LOG.append({"action": "register_success", "user_id": uid, "email": email, "ts": time.time()})
        if plan == "pro" or plan == "enterprise":
            AUDIT_LOG.append({"action": "paid_signup", "user_id": uid, "plan": plan, "ts": time.time()})
        if email in ADMIN_EMAILS:
            user["status"] = "active"
            user["role"] = "admin"
        return {"status": "ok", "user_id": uid}

    def login(self, email, password, ip_address):
        if not email or not password:
            return {"status": "error", "message": "Missing credentials"}
        found = None
        for uid, u in self.users.items():
            if u["email"].lower() == email.lower():
                found = u
                break
        if found is None:
            AUDIT_LOG.append({"action": "login_failed", "reason": "no_user", "email": email, "ip": ip_address, "ts": time.time()})
            return {"status": "error", "message": "Invalid credentials"}
        if found["status"] == "banned":
            AUDIT_LOG.append({"action": "login_failed", "reason": "banned", "user_id": found["id"], "ts": time.time()})
            return {"status": "error", "message": "Account banned"}
        if found["status"] == "inactive":
            return {"status": "error", "message": "Account inactive"}
        if found["status"] == "pending":
            return {"status": "error", "message": "Please verify your email first"}
        attempts_key = email.lower()
        if attempts_key in FAILED_ATTEMPTS:
            recent = [t for t in FAILED_ATTEMPTS[attempts_key] if time.time() - t < 900]
            FAILED_ATTEMPTS[attempts_key] = recent
            if len(recent) >= self.config["max_login_attempts"]:
                AUDIT_LOG.append({"action": "login_failed", "reason": "rate_limit", "user_id": found["id"], "ts": time.time()})
                return {"status": "error", "message": "Too many attempts, try again later"}
        pw_hash = hashlib.sha256((found["salt"] + password).encode()).hexdigest()
        if pw_hash != found["password_hash"]:
            FAILED_ATTEMPTS.setdefault(attempts_key, []).append(time.time())
            AUDIT_LOG.append({"action": "login_failed", "reason": "bad_password", "user_id": found["id"], "ip": ip_address, "ts": time.time()})
            return {"status": "error", "message": "Invalid credentials"}
        token = uuid.uuid4().hex
        self.sessions[token] = {
            "user_id": found["id"],
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=self.config["session_hours"])).isoformat(),
            "ip": ip_address,
        }
        found["last_login"] = datetime.utcnow().isoformat()
        found["login_count"] += 1
        AUDIT_LOG.append({"action": "login_success", "user_id": found["id"], "ts": time.time()})
        if attempts_key in FAILED_ATTEMPTS:
            del FAILED_ATTEMPTS[attempts_key]
        return {"status": "ok", "token": token, "user_id": found["id"], "role": found["role"]}

    def update_profile(self, user_id, updates):
        """Update profile. Updates is a dict of fields."""
        if user_id not in self.users:
            return {"status": "error", "message": "User not found"}
        u = self.users[user_id]
        if "country" in updates:
            u["profile"]["address"]["country"] = updates["country"]
            u["country"] = updates["country"]
        if "city" in updates:
            u["profile"]["address"]["city"] = updates["city"]
        if "zip" in updates:
            u["profile"]["address"]["zip"] = updates["zip"]
        if "bio" in updates:
            if len(updates["bio"]) > 500:
                return {"status": "error", "message": "Bio too long"}
            u["profile"]["bio"] = updates["bio"]
        if "phone" in updates:
            u["phone"] = updates["phone"]
        if "name" in updates:
            u["name"] = updates["name"]
        AUDIT_LOG.append({"action": "profile_update", "user_id": user_id, "ts": time.time()})
        return {"status": "ok"}

    def change_password(self, user_id, old_password, new_password):
        if user_id not in self.users:
            return {"status": "error", "message": "User not found"}
        u = self.users[user_id]
        old_hash = hashlib.sha256((u["salt"] + old_password).encode()).hexdigest()
        if old_hash != u["password_hash"]:
            return {"status": "error", "message": "Wrong current password"}
        if len(new_password) < 8:
            return {"status": "error", "message": "Password too short"}
        if not re.search(r"[A-Z]", new_password):
            return {"status": "error", "message": "Password needs an uppercase letter"}
        if not re.search(r"[0-9]", new_password):
            return {"status": "error", "message": "Password needs a digit"}
        new_salt = uuid.uuid4().hex
        u["salt"] = new_salt
        u["password_hash"] = hashlib.sha256((new_salt + new_password).encode()).hexdigest()
        EMAIL_QUEUE.append({"to": u["email"], "subject": "Password changed", "body": "Your password was changed."})
        AUDIT_LOG.append({"action": "password_changed", "user_id": user_id, "ts": time.time()})
        return {"status": "ok"}

    def ban_user(self, user_id, reason):
        if user_id not in self.users:
            return {"status": "error"}
        self.users[user_id]["status"] = "banned"
        to_remove = [t for t, s in self.sessions.items() if s["user_id"] == user_id]
        for t in to_remove:
            del self.sessions[t]
        EMAIL_QUEUE.append({"to": self.users[user_id]["email"], "subject": "Account suspended", "body": reason})
        AUDIT_LOG.append({"action": "user_banned", "user_id": user_id, "reason": reason, "ts": time.time()})
        return {"status": "ok"}

    def reactivate_user(self, user_id):
        if user_id not in self.users:
            return {"status": "error"}
        self.users[user_id]["status"] = "active"
        AUDIT_LOG.append({"action": "user_reactivated", "user_id": user_id, "ts": time.time()})
        return {"status": "ok"}

    def upgrade_plan(self, user_id, new_plan, payment_amount):
        if user_id not in self.users:
            return {"status": "error"}
        if new_plan not in ["free", "pro", "enterprise"]:
            return {"status": "error", "message": "Invalid plan"}
        u = self.users[user_id]
        old_plan = u["plan"]
        u["plan"] = new_plan
        if old_plan == "free" and new_plan == "pro":
            charge = payment_amount
        elif old_plan == "free" and new_plan == "enterprise":
            charge = payment_amount
        elif old_plan == "pro" and new_plan == "enterprise":
            charge = payment_amount - 9.99
        elif old_plan == "enterprise" and new_plan == "pro":
            charge = -50.00
        elif old_plan == "pro" and new_plan == "free":
            charge = 0
        elif old_plan == "enterprise" and new_plan == "free":
            charge = 0
        else:
            charge = 0
        AUDIT_LOG.append({"action": "plan_change", "user_id": user_id, "from": old_plan, "to": new_plan, "charge": charge, "ts": time.time()})
        return {"status": "ok", "charge": charge}

    def get_user_stats(self, user_id):
        if user_id not in self.users:
            return None
        u = self.users[user_id]
        return {
            "login_count": u["login_count"],
            "plan": u["plan"],
            "status": u["status"],
            "member_since": u["created_at"],
        }

    def list_admins(self):
        result = []
        for uid, u in self.users.items():
            if u["role"] == "admin":
                result.append(u)
        return result

    def cleanup_expired_sessions(self):
        now = datetime.utcnow()
        to_remove = []
        for token, s in self.sessions.items():
            if datetime.fromisoformat(s["expires_at"]) < now:
                to_remove.append(token)
        for token in to_remove:
            del self.sessions[token]
        return len(to_remove)


def export_users_to_csv():
    """Export all users to CSV."""
    lines = ["id,email,name,status,plan"]
    for uid, u in USERS.items():
        lines.append(f"{uid},{u['email']},{u['name']},{u['status']},{u['plan']}")
    return "\n".join(lines)