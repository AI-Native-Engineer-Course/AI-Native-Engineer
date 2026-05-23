# Characterization Tests — `register_user`

> Generated from Prompt 3 of the Lecture 4.1 hands-on. Target: priority-1 function from `priority_matrix.md`.

**These tests pin current behavior, not correctness.** Some of them lock in behavior that is arguably wrong. That is intentional — they exist so that the upcoming refactor cannot silently change anything. If we want to fix a bug, we change the test deliberately, not by accident.

## Setup Assumptions

- Each test starts with `USERS`, `AUDIT_LOG`, `EMAIL_QUEUE`, and `FAILED_ATTEMPTS` cleared.
- A fresh `UserAccountManager()` instance is created per test.
- Helper: `_call(**overrides)` invokes `register_user` with sensible defaults (`email="alice@example.com"`, `password="Secret123"`, `name="Alice"`, `role="user"`, `plan="free"`, `country="US"`, `phone=None`, `marketing_opt_in=False`) overridden by kwargs.

---

## Test Cases

### 1. `test_happy_path_returns_ok_with_user_id`
- **Input:** `_call()` with all defaults.
- **Expected:** Returns `{"status": "ok", "user_id": <uuid-string>}`. `USERS` contains exactly one entry. `AUDIT_LOG` contains a `register_success` entry.
- **Pins:** The success contract — return shape, USERS write, audit emission.

### 2. `test_default_status_is_pending`
- **Input:** `_call(email="newuser@example.com")` — non-admin email.
- **Expected:** The created user record has `status == "pending"` and `role == "user"` (whatever was passed).
- **Pins:** New non-admin signups are inactive until email verification. Do not let a refactor flip the default.

### 3. `test_admin_email_silently_overrides_role_and_status` ⚠️ **PRESERVES BUGGY BEHAVIOR**
- **Input:** `_call(email="admin@example.com", role="user")`.
- **Expected:** Returns `{"status": "ok", ...}`. The created user has `role == "admin"` and `status == "active"` — *even though the caller passed `role="user"`*.
- **Pins:** The current behavior silently rewrites the caller's `role` argument when the email is in `ADMIN_EMAILS`. This is almost certainly not what a caller would expect, but production has been running this way for 18 months and there may be ops scripts that depend on it. **Do not "fix" this during refactor — change it on purpose, with a separate commit, and update this test.**

### 4. `test_paid_plan_emits_extra_audit_entry`
- **Input:** `_call(plan="pro")`.
- **Expected:** `AUDIT_LOG` contains both a `register_success` entry *and* a `paid_signup` entry, in that order.
- **Pins:** The two-entry audit pattern for paid signups. Refactor must not collapse these into a single entry — billing reconciliation queries depend on the `paid_signup` action specifically.

### 5. `test_admin_email_with_paid_plan_still_emits_paid_signup` ⚠️ **PRESERVES SUSPICIOUS BEHAVIOR**
- **Input:** `_call(email="admin@example.com", plan="pro")`.
- **Expected:** `AUDIT_LOG` contains a `paid_signup` entry, even though the user ends up with `role="admin"` and may not actually be a paying customer.
- **Pins:** The `paid_signup` log fires *before* the admin-email override block, so admin emails on paid plans still get logged as paid signups. This may be polluting billing reports. Worth confirming with finance — but for now, lock the behavior.

### 6. `test_invalid_email_returns_error_and_logs_audit`
- **Input:** `_call(email="not-an-email")`.
- **Expected:** Returns `{"status": "error", "message": "Invalid email"}`. `USERS` is empty. `AUDIT_LOG` contains a `register_failed` entry with `reason: "bad_email"`.
- **Pins:** The validation contract for email format *and* the fact that bad emails are audit-logged.

### 7. `test_short_password_logs_audit_but_missing_uppercase_does_not` ⚠️ **PRESERVES INCONSISTENT BEHAVIOR**
- **Input:** Two calls — one with `password="short"`, one with `password="lowercase123"`.
- **Expected:** Both return errors. The short-password call adds an `AUDIT_LOG` entry with `reason: "short_password"`. The missing-uppercase call adds **nothing** to `AUDIT_LOG`.
- **Pins:** Audit logging across the password validation block is inconsistent — only the length check logs. This is almost certainly an oversight, but security-monitoring queries currently filter on `reason: "short_password"` and would break if we suddenly start emitting `reason: "missing_uppercase"`. Lock and flag.

### 8. `test_duplicate_email_detection_is_case_insensitive`
- **Input:** Register `Alice@Example.com`, then attempt to register `alice@example.com`.
- **Expected:** Second call returns `{"status": "error", "message": "Email already registered"}`. Only one entry in `USERS`.
- **Pins:** Duplicate detection lower-cases both sides. Refactor that introduces a case-sensitive check (e.g., naive dict lookup by email) would silently allow two accounts per address.

### 9. `test_invalid_role_returns_error_with_no_audit_entry`
- **Input:** `_call(role="superadmin")`.
- **Expected:** Returns `{"status": "error", "message": "Invalid role"}`. `USERS` and `AUDIT_LOG` are unchanged.
- **Pins:** Role validation hard-codes the allowed list `["admin", "user", "guest", "moderator"]`. Note: this list is duplicated in `change_password` and elsewhere — see `health_report.md`. The test pins *current* behavior; the refactor will likely centralize this list, but the rejection contract must remain.

### 10. `test_successful_registration_writes_three_side_effects`
- **Input:** `_call()`.
- **Expected:**
  - `USERS` length increases by 1.
  - `AUDIT_LOG` gains exactly one `register_success` entry.
  - `EMAIL_QUEUE` gains exactly one entry with `subject == "Welcome"`.
- **Pins:** The three-way side-effect contract on the happy path. Any of these silently dropping during refactor would create a real production gap (welcome emails not sent, audit gap, user not persisted).

### 11. `test_email_with_multiple_at_signs_passes_validation` ⚠️ **PRESERVES BUGGY BEHAVIOR**
- **Input:** `_call(email="foo@bar@example.com")`.
- **Expected:** Returns `{"status": "ok", ...}` — the validator at line 65 uses `email.split("@")[-1]` and only checks the last segment for a dot. This email passes.
- **Pins:** Edge case in the email validator. RFC-compliant validation would reject this, but the current implementation accepts it, and there may be users in production whose emails got through. Lock behavior, flag for separate cleanup.

---

## Summary

11 test cases. Four (#3, #5, #7, #11) explicitly preserve known-suspicious behavior — they are **flagged with ⚠️** so a future maintainer can tell at a glance which tests pin contracts and which pin bugs. Before the refactor begins in Lecture 4.2:

1. Implement these as real `pytest` functions.
2. Run them against the *current* code. They must all pass.
3. Only then begin the refactor. Any test that breaks during refactor is a behavior change that needs an explicit decision — not a bug to fix in passing.
