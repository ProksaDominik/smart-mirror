"""PostgreSQL connection and schema setup for the SmartMirror app."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg2
import psycopg2.extras

DATABASE_URL = "postgresql://ctai:ctai@127.0.0.1:5432/projectone"

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    task_text   TEXT NOT NULL,
    due         TEXT NOT NULL DEFAULT '',
    completed   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


@contextmanager
def get_conn() -> Iterator[psycopg2.extensions.connection]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLES)


# ── Tasks ─────────────────────────────────────────────────────────────────────

def load_tasks() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, task_text AS text, due, completed, created_at::text FROM tasks ORDER BY created_at DESC;")
            return [dict(r) for r in cur.fetchall()]


def save_task(task: dict) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasks (id, task_text, due, completed, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                    SET task_text = EXCLUDED.task_text,
                        due = EXCLUDED.due,
                        completed = EXCLUDED.completed;
                """,
                (task["id"], task["text"], task.get("due", ""), task.get("completed", False), task.get("created_at")),
            )


def save_all_tasks(tasks: list[dict]) -> None:
    for task in tasks:
        save_task(task)


def delete_task(task_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = %s;", (task_id,))
