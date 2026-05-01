# TaskFlow Mini — Product Requirements Document

**Author:** Product Management
**Status:** Draft v1.0 — MVP scope
**Last updated:** April 30, 2026

---

## 1. Executive Summary

TaskFlow Mini is a lightweight, single-team task tracker purpose-built for small engineering teams (5–15 people) who find Jira, Linear, and Asana too heavyweight for their day-to-day workflow. It provides a fast, no-ceremony way to create, assign, status, and filter tasks via a single-page web app backed by a Node.js/Express server and SQLite. To minimize setup friction for trusted internal teams, the MVP intentionally omits authentication, notifications, and multi-team support. **Success metric:** ≥ 80% of pilot teams complete at least 20 task status transitions per week within 30 days of adoption.

---

## 2. User Personas

### Persona 1 — Maya, Engineering Team Lead

- **Role:** Tech lead managing 8 engineers on a platform team.
- **Goals:**
  - See at a glance what everyone is working on.
  - Assign new work in seconds, without filling out ten fields.
  - Identify blockers before stand-up.
- **Frustrations:**
  - Jira's bloat and slow page loads.
  - Mandatory fields and configuration overhead that don't reflect how her team actually works.
  - Time spent administering the tool instead of shipping software.

### Persona 2 — Devin, Software Engineer (IC)

- **Role:** Backend engineer, individual contributor on Maya's team.
- **Goals:**
  - See only the tasks assigned to him.
  - Move a task from "In Progress" to "Done" in one click.
  - Stay in his editor as much as possible.
- **Frustrations:**
  - Context-switching to update tracker state.
  - Tools that lag behind his typing.
  - Clunky filters that require building a saved query just to see his own work.

---

## 3. User Stories

| # | Priority | Story |
|---|----------|-------|
| 1 | **P0** | As a team member, I want to create a task with a title so that work is captured quickly. |
| 2 | **P0** | As a team member, I want to see a list of all open tasks so that I know what's in flight. |
| 3 | **P0** | As a team lead, I want to assign a task to a teammate so that ownership is clear. |
| 4 | **P0** | As a team member, I want to change a task's status (Todo → In Progress → Done) so that progress is visible. |
| 5 | **P0** | As a team member, I want to filter the list by assignee so that I can focus on my own work. |
| 6 | **P1** | As a team member, I want to add a description to a task so that context isn't lost. |
| 7 | **P1** | As a team lead, I want to set a priority on a task (Low / Med / High) so that the team works on the right things first. |
| 8 | **P2** | As a team member, I want to delete a task so that the board stays clean. |

---

## 4. Acceptance Criteria (Gherkin)

### Story 1 — Create task (P0)
- **GIVEN** I am viewing the task list, **WHEN** I click "+ New Task" and submit a non-empty title, **THEN** the task is created and visible within 100 ms.
- **GIVEN** the new-task title input is empty, **WHEN** I attempt to submit, **THEN** the form is rejected with an inline error and no task is created.
- **GIVEN** I successfully create a task, **WHEN** the response returns, **THEN** the task appears at the top of the list with status "Todo" and no assignee.

### Story 2 — View task list (P0)
- **GIVEN** up to 500 tasks exist in the database, **WHEN** I load the app, **THEN** all open tasks render within 100 ms p95.
- **GIVEN** there are zero tasks, **WHEN** I load the app, **THEN** I see an empty-state prompt encouraging me to create the first task.
- **GIVEN** another teammate creates a task, **WHEN** I refresh the page, **THEN** the new task appears in my list.

### Story 3 — Assign task (P0)
- **GIVEN** I am viewing a task, **WHEN** I select an assignee from the dropdown, **THEN** the assignee badge updates and persists within 100 ms.
- **GIVEN** a task has an assignee, **WHEN** I select "Unassigned", **THEN** the assignee is cleared and the badge is removed.
- **GIVEN** the assignee dropdown is open, **WHEN** I type a name fragment, **THEN** the list filters to matching teammates in real time.

### Story 4 — Change status (P0)
- **GIVEN** a task is in "Todo", **WHEN** I click the status toggle, **THEN** it advances to "In Progress" and persists within 100 ms.
- **GIVEN** a task is in "Done", **WHEN** I click the status toggle, **THEN** it cycles back to "Todo".
- **GIVEN** the status update API call fails, **WHEN** the error is returned, **THEN** the UI reverts to the prior status and shows an error toast.

### Story 5 — Filter by assignee (P0)
- **GIVEN** the task list shows all tasks, **WHEN** I select my name in the assignee filter, **THEN** only tasks assigned to me are shown.
- **GIVEN** a filter is active, **WHEN** I click "Clear filter", **THEN** all tasks are shown again.
- **GIVEN** I select "Unassigned" in the filter, **WHEN** the list updates, **THEN** only tasks with no assignee are shown.

### Story 6 — Add description (P1)
- **GIVEN** I am viewing a task, **WHEN** I edit the description and blur the field, **THEN** the text is persisted within 100 ms.
- **GIVEN** a description exists, **WHEN** I view the task, **THEN** the description renders with line breaks preserved and HTML escaped.
- **GIVEN** a description exceeds 5,000 characters, **WHEN** I attempt to save, **THEN** the save is rejected with a length-error message and no truncation occurs.

### Story 7 — Set priority (P1)
- **GIVEN** I am viewing a task, **WHEN** I select a priority (Low / Med / High), **THEN** a colored badge appears on the task within 100 ms.
- **GIVEN** no priority has been set, **WHEN** I view the task in the list, **THEN** no priority badge is rendered.
- **GIVEN** I sort the list by priority, **WHEN** the list reorders, **THEN** the order is High → Med → Low → none, top-to-bottom.

### Story 8 — Delete task (P2)
- **GIVEN** I click the delete icon on a task, **WHEN** a confirmation dialog appears, **THEN** the task is only deleted after I confirm.
- **GIVEN** I confirm the deletion, **WHEN** the API responds successfully, **THEN** the task is removed from the list within 100 ms.
- **GIVEN** the delete API call fails, **WHEN** the error is returned, **THEN** the task is restored in the list and an error toast appears.

---

## 5. Non-Functional Requirements

### Performance
- Task list render: **< 100 ms p95** for lists of up to 500 tasks on a modern laptop.
- All write operations (create / update / delete) acknowledge within **100 ms p95** against a local SQLite instance.
- Initial bundle: HTML + JS + CSS combined under **200 KB gzipped**.
- Backend handles ≥ 50 RPS sustained on a single 1-vCPU node.

### Security
- All task fields HTML-escaped on render to prevent stored XSS.
- 100% of database queries use parameterized statements; no string concatenation in SQL.
- HTTPS required in any non-localhost deployment.
- No-auth assumption is **documented prominently** in the README and admin UI: app must be deployed only on trusted internal networks (e.g., VPN, Tailscale, office LAN).
- CORS restricted to the configured frontend origin.

### Scale
- Target operating envelope: 15 concurrent users, up to 1,000 tasks per database.
- SQLite configured with **WAL mode** to allow concurrent reads during writes.
- Stateless Express backend — a single Node process is sufficient at this scale; horizontal scaling is explicitly not required.

### Reliability & Operations
- Daily SQLite snapshot via cron, retained for 7 days (operator-provided script).
- Structured JSON request logs with a per-request UUID.
- `GET /healthz` returns 200 when the DB is reachable, 503 otherwise.
- Graceful shutdown drains in-flight requests within 5 seconds.

### Compliance
- None for MVP. No PII beyond free-text user names is stored. No data residency or audit-log requirements in scope.

---

## 6. Out of Scope (MVP)

The following are explicitly **not** being built in v1, and will be revisited post-launch based on pilot feedback:

1. **Authentication, user accounts, and permissions** — no login, password reset, SSO, or role-based access. Users are identified by free-text name only.
2. **Multi-team / multi-tenant support** — one team per database; no workspaces, organizations, or project hierarchies.
3. **Notifications** — no email, Slack, webhook, or in-app push notifications for assignments, mentions, or status changes.
4. **Comments, attachments, mentions, or activity feed** — tasks consist of title, description, status, assignee, and priority only.
5. **Reporting, analytics, exports, or burndown charts** — no aggregated views, CSV export, or dashboards beyond the task list itself.
