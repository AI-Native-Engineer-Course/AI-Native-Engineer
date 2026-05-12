# Health Report — `user_account_service.py`

> Generated from Prompt 1 of the Lecture 4.1 hands-on. Source: 281-line single-file module containing `UserAccountManager` plus four legacy helpers.

## Smell Inventory

| SMELL | LINES | RISK | FIX |
|-------|-------|------|-----|
| God Class | `UserAccountManager` (55–274) | **High** | Split into `AuthService`, `ProfileService`, `BillingService`, `AuditLogger`, `EmailDispatcher`. The class currently owns registration, authentication, session lifecycle, profile mutation, plan billing, banning, audit logging, and CSV export. |
| Long Method | `register_user` (63–115) | **High** | Extract `_validate_email`, `_validate_password`, `_check_duplicate_email`, `_build_user_record`, `_dispatch_welcome` as private helpers. Currently 8 sequential validation blocks plus user construction plus three side-effect dispatches in one function. |
| Long Method | `login` (117–159) | **High** | Extract `_find_user_by_email`, `_check_login_allowed`, `_record_failed_attempt`, `_create_session`. Authentication, status gating, rate limiting, password verification, and session creation are interleaved. |
| Shotgun Surgery | Status strings `"active"` / `"banned"` / `"inactive"` / `"pending"` scattered across `register_user`, `login`, `ban_user`, `reactivate_user` | **High** | Introduce `UserStatus` enum. Adding a new state (e.g., `"locked_for_review"`) currently requires lock-step edits in at least 4 methods, with no compiler help to catch a miss. |
| Shotgun Surgery | Password rules duplicated between `register_user` (75–80) and `change_password` (190–195) | **Medium** | Extract a single `validate_password_strength()` helper. Any policy change (length, character class) currently requires editing two places, and they have already drifted in error message wording. |
| Primitive Obsession | `email`, `role`, `plan`, `status`, `payment_amount` all passed and stored as raw `str` / `float` | **Medium** | Introduce `Email`, `UserRole(Enum)`, `Plan(Enum)`, `UserStatus(Enum)`, and `Money` value objects. Validation currently happens defensively at every entry point because the types carry no constraints. |
| Feature Envy | `update_profile` (165–170) reaches into `u["profile"]["address"]["country"]` / `["city"]` / `["zip"]` | **Medium** | Extract `Profile` and `Address` classes that own their own mutation. Bonus: line 167 keeps a duplicate copy at `u["country"]` — a consistency bug waiting to happen. |
| Feature Envy | `upgrade_plan` (222–245) is almost entirely billing logic living on the user manager | **Medium** | Move proration to `BillingService.calculate_plan_change(old_plan, new_plan, payment_amount)`. The user manager should ask the billing service for a charge, not compute it. |
| Dead Code | `_legacy_md5_hash` (30), `_old_email_format_check` (35), `_format_user_for_export_v1` (40), `_calculate_legacy_discount` (45) | **Low** | Delete after `grep`-confirming no callers across the wider codebase. All four are commented as legacy. |
| Dead Code | Unused imports: `json` (line 10), `smtplib` (line 12) | **Low** | Remove imports. The `# noqa: F401` suppressions suggest they were knowingly retained — confirm with original author before deleting. |

## Follow-Up: Highest Regression Risk

> Of the smells above, which poses the highest regression risk and why?

**`register_user` (Long Method) combined with the God Class structure around it.** It is the single highest-risk smell because it interleaves email validation, password hashing, duplicate detection, audit logging, email dispatch, *and* a silent admin-promotion side effect — all in one function on the critical signup path. Any extraction has to preserve the implicit ordering of side effects (audit log entry → user creation → welcome email → admin override), and the function's many early returns make it easy to drop one of those side effects during refactor without any test catching it.
