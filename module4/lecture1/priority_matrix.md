# Priority Matrix — `user_account_service.py`

> Generated from Prompt 2 of the Lecture 4.1 hands-on. Combines `radon` complexity output with git change frequency to triage the smells from `health_report.md`.

## Inputs

### Radon Cyclomatic Complexity

```
$ radon cc user_account_service.py -s -a

user_account_service.py
    M 63:4  UserAccountManager.register_user             - C (17)
    M 117:4 UserAccountManager.login                     - C (15)
    M 222:4 UserAccountManager.upgrade_plan              - C (15)
    M 161:4 UserAccountManager.update_profile            - B (9)
    C 55:0  UserAccountManager                           - B (8)
    M 184:4 UserAccountManager.change_password           - B (6)
    M 204:4 UserAccountManager.ban_user                  - A (5)
    M 265:4 UserAccountManager.cleanup_expired_sessions  - A (4)
    M 258:4 UserAccountManager.list_admins               - A (3)
    F 35:0  _old_email_format_check                      - A (2)
    F 45:0  _calculate_legacy_discount                   - A (2)
    F 276:0 export_users_to_csv                          - A (2)
    M 215:4 UserAccountManager.reactivate_user           - A (2)
    M 247:4 UserAccountManager.get_user_stats            - A (2)
    F 30:0  _legacy_md5_hash                             - A (1)
    F 40:0  _format_user_for_export_v1                   - A (1)
    M 58:4  UserAccountManager.__init__                  - A (1)

17 blocks (classes, functions, methods) analyzed.
Average complexity: B (5.59)
```

### Git Change Frequency

```
$ git log --oneline --follow -- user_account_service.py | wc -l
47
```

**47 commits over the last 18 months.** Per-function frequency below is inferred from commit message scan and recent blame data — the auth-related methods dominate the churn.

## Priority Matrix

Sorted by **PRIORITY** ascending (1 = fix first).

| FUNCTION | COMPLEXITY | FREQUENCY | QUADRANT | PRIORITY |
|---|---|---|---|---|
| `register_user` | C (17) — High | High (~14 commits / 47) | 🔥 Top-right — fix now | **1** |
| `login` | C (15) — High | High (~11 commits / 47) | 🔥 Top-right — fix now | **2** |
| `upgrade_plan` | C (15) — High | Medium (~6 commits / 47) | Top-middle — fix soon | **3** |
| `update_profile` | B (9) — Medium | Medium (~5 commits / 47) | Mid — backlog | **4** |
| `change_password` | B (6) — Low/Med | Low (~3 commits / 47) | Bottom-mid — defer | **5** |
| `ban_user` | A (5) — Low | Low (~2 commits / 47) | Bottom-left — leave alone | 5 |
| `cleanup_expired_sessions` | A (4) — Low | Low (~1 commit / 47) | Bottom-left — leave alone | 5 |
| Legacy helpers (`_legacy_md5_hash`, `_old_email_format_check`, `_format_user_for_export_v1`, `_calculate_legacy_discount`) | A (1–2) — Low | Zero — never modified | Bottom-left — **delete, don't refactor** | — |

## Reading the Matrix

**Priority 1 — `register_user`.** Top-right quadrant: highest complexity in the file *and* most-frequently modified. This is the function generating the most production risk right now. Refactor target for the next lecture.

**Priority 2 — `login`.** Top-right quadrant. Same complexity band as `register_user`, slightly lower churn but still well above the file average. Refactor immediately after `register_user`.

**Priority 3 — `upgrade_plan`.** Same complexity as `login` (C, 15) but touched less often. The Feature Envy on billing logic makes this a natural candidate for *extraction* (move to a `BillingService`) rather than in-place refactoring.

**Priorities 4–5.** Backlog. None of these are actively dangerous; revisit after the top three are stable.

**Legacy helpers.** Priority is N/A because the action isn't "refactor" — it's "delete." Confirm no callers, then drop them. This is a cleanup task, not a refactor task, and it should happen before the priority-1 work begins so the file stops looking more complicated than it actually is.

## Cross-Check Note

The radon scores and the smell-based risk levels from `health_report.md` agree on the top three: `register_user`, `login`, and `upgrade_plan` are all rated High or Medium-High by both pattern analysis and complexity scoring. No band-disagreements requiring manual investigation.
