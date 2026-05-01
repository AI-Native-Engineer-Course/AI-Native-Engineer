const express = require('express');
const Database = require('better-sqlite3');
const fs = require('fs');
const path = require('path');

const app = express();
const db = new Database('db/taskflow.db');
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');         // critical — OFF by default in SQLite

app.use(express.json());
app.use(express.static('public'));

const TEAM_ID = 1;                       // single-team MVP per PRD §6

// GET /api/tasks — list tasks with comma-separated assignee names
app.get('/api/tasks', (req, res) => {
  const rows = db.prepare(`
    SELECT
      t.id,
      t.title,
      t.status,
      t.priority,
      GROUP_CONCAT(u.name, ', ') AS assignee
    FROM tasks t
    LEFT JOIN task_assignees ta ON ta.task_id = t.id
    LEFT JOIN users u           ON u.id       = ta.user_id
    WHERE t.team_id = ?
    GROUP BY t.id
    ORDER BY
      CASE t.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
      t.id DESC
  `).all(TEAM_ID);
  res.json(rows);
});

// POST /api/tasks — create task and (optionally) assign one user atomically
app.post('/api/tasks', (req, res) => {
  const { title, priority = 'medium', assignee_id = null } = req.body;

  if (!title || title.length < 3) {
    return res.status(400).json({ error: 'title must be 3+ chars' });
  }
  if (!['low', 'medium', 'high'].includes(priority)) {
    return res.status(400).json({ error: "priority must be 'low', 'medium', or 'high'" });
  }

  const insertTask = db.prepare(`
    INSERT INTO tasks (team_id, title, status, priority)
    VALUES (?, ?, 'open', ?)
  `);
  const insertAssignee = db.prepare(`
    INSERT INTO task_assignees (task_id, user_id) VALUES (?, ?)
  `);

  const create = db.transaction(() => {
    const info = insertTask.run(TEAM_ID, title, priority);
    if (assignee_id != null) insertAssignee.run(info.lastInsertRowid, assignee_id);
    return info.lastInsertRowid;
  });

  try {
    res.status(201).json({ id: create() });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

// GET /api/diagrams — unchanged
app.get('/api/diagrams', (req, res) => {
  const dir = path.join(__dirname, 'docs', 'diagrams');
  res.json({
    architecture: fs.readFileSync(path.join(dir, 'architecture.mmd'), 'utf8'),
    sequence:     fs.readFileSync(path.join(dir, 'sequence.mmd'),     'utf8'),
    er:           fs.readFileSync(path.join(dir, 'er.mmd'),           'utf8'),
  });
});

app.listen(3000, () => console.log('TaskFlow Mini → http://localhost:3000'));