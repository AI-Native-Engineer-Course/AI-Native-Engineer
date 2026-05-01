-- =====================================================================
-- TaskFlow Mini — SQLite schema (MVP)
-- Target: SQLite 3.37+ via better-sqlite3 (Node.js)
-- Run once on a fresh database. No migrations tooling for MVP.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Connection-level pragmas.
-- These are NOT persisted in the database file. The application MUST
-- set them on every new connection in its bootstrap code, e.g.:
--
--   const db = new Database('taskflow.db');
--   db.pragma('journal_mode = WAL');
--   db.pragma('foreign_keys = ON');
--   db.pragma('synchronous = NORMAL');
--   db.pragma('busy_timeout = 5000');
--
-- foreign_keys = ON is critical — it's OFF by default in SQLite and
-- without it none of the ON DELETE rules below will fire.
-- ---------------------------------------------------------------------
PRAGMA journal_mode = WAL;       -- PRD §5: concurrent reads during writes
PRAGMA foreign_keys = ON;        -- enforce FK constraints
PRAGMA synchronous  = NORMAL;    -- safe under WAL, faster than FULL
PRAGMA busy_timeout = 5000;      -- avoid SQLITE_BUSY under contention

-- =====================================================================
-- TABLES (created in dependency order)
-- =====================================================================

-- Top-level container. One row in MVP; table exists for future multi-team.
CREATE TABLE teams (
  id          INTEGER PRIMARY KEY,
  name        TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
  created_at  TEXT    NOT NULL
              DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

-- Members of a team. No password column — auth is out of scope per PRD §6.
CREATE TABLE users (
  id          INTEGER PRIMARY KEY,
  team_id     INTEGER NOT NULL
              REFERENCES teams(id) ON DELETE RESTRICT,
  name        TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
  email       TEXT    NOT NULL UNIQUE
              CHECK (email LIKE '%_@_%.__%'),
  role        TEXT    NOT NULL
              CHECK (role IN ('lead', 'member')),
  created_at  TEXT    NOT NULL
              DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

-- Core entity. Driven by the P0 stories in the PRD.
CREATE TABLE tasks (
  id           INTEGER PRIMARY KEY,
  team_id      INTEGER NOT NULL
               REFERENCES teams(id) ON DELETE RESTRICT,
  title        TEXT    NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  description  TEXT    CHECK (description IS NULL OR length(description) <= 5000),
  status       TEXT    NOT NULL DEFAULT 'open'
               CHECK (status IN ('open', 'in_progress', 'done')),
  priority     TEXT    NOT NULL DEFAULT 'medium'
               CHECK (priority IN ('low', 'medium', 'high')),
  created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
  due_date     TEXT    CHECK (due_date IS NULL OR
                              due_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  created_at   TEXT    NOT NULL
               DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at   TEXT    NOT NULL
               DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

-- Auto-bump updated_at whenever a row is modified.
-- The WHEN guard prevents trigger recursion (the recursive UPDATE will
-- have OLD.updated_at != NEW.updated_at and skip). It also lets the
-- application override updated_at explicitly when needed (seeds, imports).
CREATE TRIGGER tasks_set_updated_at
AFTER UPDATE ON tasks
FOR EACH ROW
WHEN OLD.updated_at = NEW.updated_at
BEGIN
  UPDATE tasks
     SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
   WHERE id = NEW.id;
END;

-- Junction resolving the M:N between tasks and users.
-- A task can have many assignees; a user can be assigned to many tasks.
-- WITHOUT ROWID is appropriate: composite PK, all-metadata payload, small rows.
CREATE TABLE task_assignees (
  task_id      INTEGER NOT NULL
               REFERENCES tasks(id) ON DELETE CASCADE,
  user_id      INTEGER NOT NULL
               REFERENCES users(id) ON DELETE CASCADE,
  assigned_at  TEXT    NOT NULL
               DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  assigned_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
  PRIMARY KEY (task_id, user_id)
) STRICT, WITHOUT ROWID;

-- One-to-many from tasks. Out of MVP scope per PRD §6 #4 — included here
-- for the planned P1 collaboration stories.
CREATE TABLE comments (
  id          INTEGER PRIMARY KEY,
  task_id     INTEGER NOT NULL
              REFERENCES tasks(id) ON DELETE CASCADE,
  author_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
  body        TEXT    NOT NULL CHECK (length(body) BETWEEN 1 AND 10000),
  created_at  TEXT    NOT NULL
              DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

-- =====================================================================
-- INDEXES
-- Each one is justified by a specific PRD story or query pattern.
-- =====================================================================

-- Story 2 (view all open tasks): the canonical list query is
--   WHERE team_id = ? AND status != 'done'
-- A composite (team_id, status) lets the planner satisfy this in one
-- index seek and supports per-status filtering for kanban-style views.
CREATE INDEX idx_tasks_team_status
  ON tasks(team_id, status);

-- Story 5 (filter by assignee — "show me my tasks"): the task_assignees
-- PK is leftmost-task_id, so user_id needs its own index for the
-- reverse direction "tasks assigned to user X".
CREATE INDEX idx_task_assignees_user
  ON task_assignees(user_id);

-- Story 7 (sort by priority): supports ORDER BY priority within a team.
-- Note: SQLite sorts the priority TEXT enum lexicographically, so
-- 'high' < 'low' < 'medium' alphabetically — the application must use
-- a CASE expression or a join to a rank table to get High → Med → Low.
-- This index still accelerates the sort regardless of CASE ordering.
CREATE INDEX idx_tasks_team_priority
  ON tasks(team_id, priority);

-- Story 3 (assignee dropdown lists all teammates): the dropdown query
-- is SELECT id, name FROM users WHERE team_id = ? ORDER BY name.
-- Also accelerates user-lookup pages in any future admin UI.
CREATE INDEX idx_users_team
  ON users(team_id);

-- Comments are rendered chronologically per task; supports the planned
-- P1 thread view (SELECT * FROM comments WHERE task_id = ? ORDER BY created_at).
CREATE INDEX idx_comments_task_created
  ON comments(task_id, created_at);

-- =====================================================================
-- SEED DATA
-- 1 team, 3 users, 5 tasks, plus a few assignments to exercise the M:N.
-- IDs are explicit for reproducibility and to allow re-running the seed
-- block inside a transaction wrapper if the schema is rebuilt.
-- =====================================================================

INSERT INTO teams (id, name) VALUES
  (1, 'Platform Engineering');

INSERT INTO users (id, team_id, name, email, role) VALUES
  (1, 1, 'Maya Chen',    'maya@example.com',   'lead'),
  (2, 1, 'Devin Park',   'devin@example.com',  'member'),
  (3, 1, 'Riley Okafor', 'riley@example.com',  'member');

INSERT INTO tasks (id, team_id, title, description, status, priority, created_by, due_date) VALUES
  (1, 1, 'Migrate auth service to new IdP',
         'Cut over from legacy SSO; coordinate with security team.',
         'in_progress', 'high',   1, '2026-05-15'),
  (2, 1, 'Fix flaky test in payment-gateway suite',
         'Intermittent failure on retry-after-timeout test.',
         'open',        'medium', 1, NULL),
  (3, 1, 'Write postmortem for April 22 incident',
         NULL,
         'open',        'high',   1, '2026-05-02'),
  (4, 1, 'Upgrade better-sqlite3 to v11',
         'Check for breaking changes in prepared-statement API.',
         'done',        'low',    2, NULL),
  (5, 1, 'Document new on-call rotation',
         'Publish to internal wiki and link from #platform.',
         'open',        'medium', 2, '2026-05-10');

-- Multi-assignee demo: task 1 has two owners, task 3 and 5 have one
-- each, task 2 and 4 are unassigned. Covers the "Unassigned" filter case.
INSERT INTO task_assignees (task_id, user_id, assigned_by) VALUES
  (1, 2, 1),
  (1, 3, 1),
  (3, 1, 1),
  (5, 2, 1);
  