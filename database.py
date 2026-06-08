import logging
import sqlite3 as sq
import shutil
from pathlib import Path

from config import ADMIN_ID


logger = logging.getLogger(__name__)


def _normalize_user_id(user_id) -> str:
    return str(user_id)


def resolve_users_db_path() -> Path:
    db_name = "Users.db"
    cwd = Path.cwd()
    shared_candidates = [
        cwd / "shared",
        cwd.parent / "shared",
        cwd.parent.parent / "shared",
    ]
    shared_dir = next(
        (candidate for candidate in shared_candidates if candidate.is_dir()),
        None,
    )

    if shared_dir is None:
        return cwd / db_name

    local_db = cwd / db_name
    shared_db = shared_dir / db_name

    if not shared_db.exists() and local_db.exists():
        shared_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_db, shared_db)

    return shared_db


def _ensure_user_schema() -> None:
    cur.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in cur.fetchall()}

    if "joined_at" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN joined_at TEXT")

    if "is_admin" not in columns:
        cur.execute(
            "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
        )

    cur.execute(
        "UPDATE users SET joined_at = COALESCE(joined_at, CURRENT_TIMESTAMP)"
    )
    cur.execute(
        "UPDATE users SET is_admin = 1 WHERE id = ?",
        (_normalize_user_id(ADMIN_ID),),
    )
    db.commit()


async def db_connect() -> None:
    global db, cur
    db = sq.connect(resolve_users_db_path())
    cur = db.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
            id TEXT PRIMARY KEY UNIQUE ON CONFLICT IGNORE,
            name TEXT,
            joined_at TEXT,
            is_admin INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    _ensure_user_schema()
    db.commit()


async def get_user(user_id) -> tuple | None:
    cur.execute("SELECT * FROM users WHERE id=?", (_normalize_user_id(user_id),))
    return cur.fetchone()


async def get_users() -> list[tuple]:
    return cur.execute(
        """
        SELECT id, name, joined_at, is_admin
        FROM users
        ORDER BY datetime(joined_at) DESC, id DESC
        """
    ).fetchall()


async def get_user_ids() -> list[int]:
    rows = cur.execute("SELECT id FROM users").fetchall()
    return [int(row[0]) for row in rows]


async def del_user(user_id):
    cur.execute(
        "DELETE from users where id = ?",
        (_normalize_user_id(user_id),),
    )
    db.commit()


async def check_id(user_id) -> bool:
    cur.execute("SELECT 1 FROM users WHERE id=?", (_normalize_user_id(user_id),))
    return cur.fetchone() is not None


async def add_id(user_id):
    user_id = _normalize_user_id(user_id)
    cur.execute("SELECT COUNT(*) FROM users WHERE id = ?", (user_id,))
    result = cur.fetchone()[0]

    if result == 0:
        cur.execute(
            "INSERT INTO users (id, joined_at) VALUES (?, CURRENT_TIMESTAMP)",
            (user_id,),
        )
        if user_id == _normalize_user_id(ADMIN_ID):
            cur.execute(
                "UPDATE users SET is_admin = 1 WHERE id = ?",
                (user_id,),
            )
        db.commit()


async def update(user_id, first_name):
    await add_id(user_id)
    cur.execute(
        "UPDATE users SET name=? WHERE id=?",
        (first_name, _normalize_user_id(user_id)),
    )
    db.commit()


async def is_admin(user_id) -> bool:
    user_id = _normalize_user_id(user_id)
    if user_id == _normalize_user_id(ADMIN_ID):
        return True

    cur.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    return bool(row and row[0])


async def set_admin(user_id, value: bool) -> bool:
    user_id = _normalize_user_id(user_id)
    if user_id == _normalize_user_id(ADMIN_ID) and not value:
        return False

    cur.execute(
        "UPDATE users SET is_admin = ? WHERE id = ?",
        (1 if value else 0, user_id),
    )
    db.commit()
    return cur.rowcount > 0


async def get_admin_users() -> list[tuple]:
    return cur.execute(
        """
        SELECT id, name, is_admin
        FROM users
        WHERE is_admin = 1
        ORDER BY id
        """
    ).fetchall()


async def get_stats() -> dict[str, int]:
    total_users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    named_users = cur.execute(
        "SELECT COUNT(*) FROM users WHERE name IS NOT NULL AND TRIM(name) != ''"
    ).fetchone()[0]
    admins_total = cur.execute(
        "SELECT COUNT(*) FROM users WHERE is_admin = 1"
    ).fetchone()[0]
    joined_today = cur.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE date(joined_at, 'localtime') = date('now', 'localtime')
        """
    ).fetchone()[0]
    joined_week = cur.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE datetime(joined_at) >= datetime('now', '-7 days')
        """
    ).fetchone()[0]

    return {
        "total_users": total_users,
        "named_users": named_users,
        "admins_total": admins_total,
        "joined_today": joined_today,
        "joined_week": joined_week,
    }
