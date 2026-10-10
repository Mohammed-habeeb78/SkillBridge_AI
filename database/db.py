"""
database/db.py — SQLite database layer for SkillBridge AI.

Responsibilities:
  - Create and migrate the schema on first run.
  - Provide simple CRUD helpers used by other modules.
  - Never expose raw connection objects outside this module.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATABASE_FILE, DATABASE_DIR

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name    TEXT    NOT NULL,
    email           TEXT    UNIQUE,
    education_level TEXT,
    degree          TEXT,
    branch          TEXT,
    graduation_year INTEGER,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_skills (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id      TEXT    NOT NULL,   -- canonical skill key
    skill_label   TEXT    NOT NULL,
    proficiency   TEXT    DEFAULT 'claimed',  -- claimed | beginner | intermediate | advanced
    source        TEXT    DEFAULT 'manual',   -- manual | resume | assessment
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL,
    description TEXT,
    skills_used TEXT,   -- JSON array of skill_ids
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_certifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    issuer      TEXT,
    year        INTEGER,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assessments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id         TEXT    NOT NULL,
    role_title      TEXT    NOT NULL,
    readiness_score REAL    NOT NULL,
    matched_skills  TEXT,   -- JSON array
    missing_skills  TEXT,   -- JSON array
    partial_skills  TEXT,   -- JSON array
    score_breakdown TEXT,   -- JSON object
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS roadmap_tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id   INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id        TEXT    NOT NULL,
    skill_label     TEXT    NOT NULL,
    stage           INTEGER NOT NULL DEFAULT 1,
    priority        INTEGER NOT NULL DEFAULT 1,
    status          TEXT    NOT NULL DEFAULT 'pending',  -- pending | in_progress | completed
    completed_at    TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id      TEXT    NOT NULL,
    score         REAL    NOT NULL,
    max_score     REAL    NOT NULL,
    answers       TEXT,   -- JSON array of {question_id, answer, correct}
    attempted_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS resume_uploads (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename     TEXT    NOT NULL,
    extracted_text TEXT,
    parsed_skills  TEXT,  -- JSON array
    status       TEXT    NOT NULL DEFAULT 'pending',  -- pending | parsed | failed
    uploaded_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_connection() -> sqlite3.Connection:
    """Return a thread-local SQLite connection with row-factory set."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables if they do not yet exist."""
    conn = _get_connection()
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.utcnow().isoformat(sep=" ", timespec="seconds")


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def create_user(display_name: str, email: Optional[str] = None,
                education_level: str = "", degree: str = "",
                branch: str = "", graduation_year: Optional[int] = None) -> int:
    """Insert a new user and return the new user id."""
    conn = _get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO users (display_name, email, education_level, degree, branch, graduation_year, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (display_name, email, education_level, degree, branch, graduation_year, _now())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_user(user_id: int) -> Optional[Dict]:
    conn = _get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_user(user_id: int, **fields) -> None:
    """Update any subset of user columns."""
    allowed = {"display_name", "email", "education_level", "degree", "branch", "graduation_year"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = _now()
    cols = ", ".join(f"{k} = ?" for k in updates)
    conn = _get_connection()
    try:
        conn.execute(f"UPDATE users SET {cols} WHERE id = ?", (*updates.values(), user_id))
        conn.commit()
    finally:
        conn.close()


def delete_user(user_id: int) -> None:
    """Hard-delete a user and all associated data (cascades)."""
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def list_users() -> List[Dict]:
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

def set_user_skills(user_id: int, skills: List[Dict]) -> None:
    """Replace all skills for a user. Each dict: {skill_id, skill_label, proficiency, source}."""
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM user_skills WHERE user_id = ?", (user_id,))
        conn.executemany(
            """INSERT INTO user_skills (user_id, skill_id, skill_label, proficiency, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(user_id, s["skill_id"], s["skill_label"],
              s.get("proficiency", "claimed"), s.get("source", "manual"), _now())
             for s in skills]
        )
        conn.commit()
    finally:
        conn.close()


def get_user_skills(user_id: int) -> List[Dict]:
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM user_skills WHERE user_id = ? ORDER BY skill_label", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def upsert_skill(user_id: int, skill_id: str, skill_label: str,
                 proficiency: str = "claimed", source: str = "manual") -> None:
    """Insert or update a single skill entry."""
    conn = _get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM user_skills WHERE user_id = ? AND skill_id = ?",
            (user_id, skill_id)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE user_skills SET proficiency = ?, source = ? WHERE id = ?",
                (proficiency, source, existing["id"])
            )
        else:
            conn.execute(
                """INSERT INTO user_skills (user_id, skill_id, skill_label, proficiency, source, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, skill_id, skill_label, proficiency, source, _now())
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Projects & Certifications
# ---------------------------------------------------------------------------

def set_user_projects(user_id: int, projects: List[Dict]) -> None:
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM user_projects WHERE user_id = ?", (user_id,))
        conn.executemany(
            """INSERT INTO user_projects (user_id, title, description, skills_used, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [(user_id, p["title"], p.get("description", ""),
              json.dumps(p.get("skills_used", [])), _now())
             for p in projects]
        )
        conn.commit()
    finally:
        conn.close()


def get_user_projects(user_id: int) -> List[Dict]:
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM user_projects WHERE user_id = ?", (user_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["skills_used"] = json.loads(d["skills_used"] or "[]")
            result.append(d)
        return result
    finally:
        conn.close()


def set_user_certifications(user_id: int, certs: List[Dict]) -> None:
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM user_certifications WHERE user_id = ?", (user_id,))
        conn.executemany(
            """INSERT INTO user_certifications (user_id, name, issuer, year, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [(user_id, c["name"], c.get("issuer", ""), c.get("year"), _now())
             for c in certs]
        )
        conn.commit()
    finally:
        conn.close()


def get_user_certifications(user_id: int) -> List[Dict]:
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM user_certifications WHERE user_id = ?", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------

def save_assessment(user_id: int, role_id: str, role_title: str,
                    readiness_score: float, matched: List, missing: List,
                    partial: List, breakdown: Dict) -> int:
    conn = _get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO assessments
               (user_id, role_id, role_title, readiness_score, matched_skills,
                missing_skills, partial_skills, score_breakdown, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, role_id, role_title, readiness_score,
             json.dumps(matched), json.dumps(missing),
             json.dumps(partial), json.dumps(breakdown), _now())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_assessments(user_id: int) -> List[Dict]:
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM assessments WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for key in ("matched_skills", "missing_skills", "partial_skills", "score_breakdown"):
                d[key] = json.loads(d[key] or "[]")
            result.append(d)
        return result
    finally:
        conn.close()


def get_latest_assessment(user_id: int, role_id: str) -> Optional[Dict]:
    conn = _get_connection()
    try:
        row = conn.execute(
            """SELECT * FROM assessments WHERE user_id = ? AND role_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, role_id)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ("matched_skills", "missing_skills", "partial_skills", "score_breakdown"):
            d[key] = json.loads(d[key] or "[]")
        return d
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Roadmap tasks
# ---------------------------------------------------------------------------

def save_roadmap_tasks(assessment_id: int, user_id: int,
                       tasks: List[Dict]) -> None:
    """tasks: list of {skill_id, skill_label, stage, priority}"""
    conn = _get_connection()
    try:
        # Remove any previous tasks for this assessment
        conn.execute("DELETE FROM roadmap_tasks WHERE assessment_id = ?", (assessment_id,))
        conn.executemany(
            """INSERT INTO roadmap_tasks
               (assessment_id, user_id, skill_id, skill_label, stage, priority, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            [(assessment_id, user_id, t["skill_id"], t["skill_label"],
              t.get("stage", 1), t.get("priority", 1), _now())
             for t in tasks]
        )
        conn.commit()
    finally:
        conn.close()


def get_roadmap_tasks(user_id: int, assessment_id: Optional[int] = None) -> List[Dict]:
    conn = _get_connection()
    try:
        if assessment_id:
            rows = conn.execute(
                """SELECT * FROM roadmap_tasks WHERE user_id = ? AND assessment_id = ?
                   ORDER BY stage, priority""",
                (user_id, assessment_id)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM roadmap_tasks WHERE user_id = ? ORDER BY stage, priority",
                (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_task_status(task_id: int, status: str) -> None:
    completed_at = _now() if status == "completed" else None
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE roadmap_tasks SET status = ?, completed_at = ? WHERE id = ?",
            (status, completed_at, task_id)
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Quiz attempts
# ---------------------------------------------------------------------------

def save_quiz_attempt(user_id: int, skill_id: str, score: float,
                      max_score: float, answers: List[Dict]) -> int:
    conn = _get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO quiz_attempts (user_id, skill_id, score, max_score, answers, attempted_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, skill_id, score, max_score, json.dumps(answers), _now())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_quiz_attempts(user_id: int, skill_id: Optional[str] = None) -> List[Dict]:
    conn = _get_connection()
    try:
        if skill_id:
            rows = conn.execute(
                "SELECT * FROM quiz_attempts WHERE user_id = ? AND skill_id = ? ORDER BY attempted_at DESC",
                (user_id, skill_id)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM quiz_attempts WHERE user_id = ? ORDER BY attempted_at DESC",
                (user_id,)
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["answers"] = json.loads(d["answers"] or "[]")
            result.append(d)
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Resume uploads
# ---------------------------------------------------------------------------

def save_resume_upload(user_id: int, filename: str,
                       extracted_text: str = "", parsed_skills: List = None,
                       status: str = "pending") -> int:
    conn = _get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO resume_uploads
               (user_id, filename, extracted_text, parsed_skills, status, uploaded_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, filename, extracted_text,
             json.dumps(parsed_skills or []), status, _now())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_resume_upload(upload_id: int, extracted_text: str,
                         parsed_skills: List, status: str) -> None:
    conn = _get_connection()
    try:
        conn.execute(
            """UPDATE resume_uploads
               SET extracted_text = ?, parsed_skills = ?, status = ?
               WHERE id = ?""",
            (extracted_text, json.dumps(parsed_skills), status, upload_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_latest_resume(user_id: int) -> Optional[Dict]:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM resume_uploads WHERE user_id = ? ORDER BY uploaded_at DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["parsed_skills"] = json.loads(d["parsed_skills"] or "[]")
        return d
    finally:
        conn.close()


def delete_resume_data(user_id: int) -> None:
    """Remove all resume uploads for a user (GDPR-style deletion)."""
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM resume_uploads WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
