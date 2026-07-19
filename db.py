"""Доступ к SQLite для ChatList."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(__file__).resolve().parent / "chatlist.db"

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS prompts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT    NOT NULL,
    text       TEXT    NOT NULL,
    tags       TEXT
);

CREATE TABLE IF NOT EXISTS models (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    api_url     TEXT    NOT NULL,
    api_key_env TEXT    NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id  INTEGER NOT NULL,
    model_id   INTEGER NOT NULL,
    response   TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id),
    FOREIGN KEY (model_id)  REFERENCES models(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_prompts_created_at ON prompts(created_at);
CREATE INDEX IF NOT EXISTS idx_results_prompt_id ON results(prompt_id);
CREATE INDEX IF NOT EXISTS idx_results_model_id ON results(model_id);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_db(db_path: Path | str | None = None) -> Path:
    """Создаёт файл БД и таблицы при первом запуске. Возвращает путь к БД."""
    path = Path(db_path) if db_path is not None else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    return path


@contextmanager
def get_connection(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    path = Path(db_path) if db_path is not None else DB_PATH
    if not path.exists():
        init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


# --- prompts ---


def add_prompt(text: str, tags: str | None = None, db_path: Path | str | None = None) -> int:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO prompts (created_at, text, tags) VALUES (?, ?, ?)",
            (_now_iso(), text, tags),
        )
        return int(cur.lastrowid)


def list_prompts(db_path: Path | str | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, created_at, text, tags FROM prompts ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def search_prompts(query: str, db_path: Path | str | None = None) -> list[dict[str, Any]]:
    pattern = f"%{query}%"
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, text, tags FROM prompts
            WHERE text LIKE ? OR IFNULL(tags, '') LIKE ?
            ORDER BY created_at DESC
            """,
            (pattern, pattern),
        ).fetchall()
        return [dict(r) for r in rows]


def get_prompt(prompt_id: int, db_path: Path | str | None = None) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT id, created_at, text, tags FROM prompts WHERE id = ?",
            (prompt_id,),
        ).fetchone()
        return _row_to_dict(row)


# --- models ---


def add_model(
    name: str,
    api_url: str,
    api_key_env: str,
    is_active: bool = True,
    db_path: Path | str | None = None,
) -> int:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO models (name, api_url, api_key_env, is_active)
            VALUES (?, ?, ?, ?)
            """,
            (name, api_url, api_key_env, 1 if is_active else 0),
        )
        return int(cur.lastrowid)


def update_model(
    model_id: int,
    name: str | None = None,
    api_url: str | None = None,
    api_key_env: str | None = None,
    is_active: bool | None = None,
    db_path: Path | str | None = None,
) -> None:
    current = get_model(model_id, db_path=db_path)
    if current is None:
        raise ValueError(f"Модель id={model_id} не найдена")

    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE models
            SET name = ?, api_url = ?, api_key_env = ?, is_active = ?
            WHERE id = ?
            """,
            (
                name if name is not None else current["name"],
                api_url if api_url is not None else current["api_url"],
                api_key_env if api_key_env is not None else current["api_key_env"],
                (
                    (1 if is_active else 0)
                    if is_active is not None
                    else current["is_active"]
                ),
                model_id,
            ),
        )


def get_model(model_id: int, db_path: Path | str | None = None) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, name, api_url, api_key_env, is_active
            FROM models WHERE id = ?
            """,
            (model_id,),
        ).fetchone()
        return _row_to_dict(row)


def list_models(db_path: Path | str | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, name, api_url, api_key_env, is_active
            FROM models ORDER BY name
            """
        ).fetchall()
        return [dict(r) for r in rows]


def list_active_models(db_path: Path | str | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, name, api_url, api_key_env, is_active
            FROM models WHERE is_active = 1 ORDER BY name
            """
        ).fetchall()
        return [dict(r) for r in rows]


def delete_model(model_id: int, db_path: Path | str | None = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM models WHERE id = ?", (model_id,))


# --- results ---


def save_results(
    prompt_id: int,
    items: list[dict[str, Any]],
    db_path: Path | str | None = None,
) -> list[int]:
    """Сохраняет выбранные ответы. items: [{model_id, response}, ...]."""
    ids: list[int] = []
    created_at = _now_iso()
    with get_connection(db_path) as conn:
        for item in items:
            cur = conn.execute(
                """
                INSERT INTO results (prompt_id, model_id, response, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (prompt_id, item["model_id"], item["response"], created_at),
            )
            ids.append(int(cur.lastrowid))
    return ids


def list_results(db_path: Path | str | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                r.id,
                r.prompt_id,
                r.model_id,
                r.response,
                r.created_at,
                p.text AS prompt_text,
                m.name AS model_name
            FROM results r
            JOIN prompts p ON p.id = r.prompt_id
            JOIN models m ON m.id = r.model_id
            ORDER BY r.created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


# --- settings ---


def get_setting(key: str, default: str | None = None, db_path: Path | str | None = None) -> str | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        return row["value"]


def set_setting(key: str, value: str | None, db_path: Path | str | None = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
