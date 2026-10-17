import secrets
import sqlite3
import sys

from auth import create_key_for, hash_password
from db import get_conn, init_db


def create_admin(name: str) -> None:
    init_db()
    try:
        with get_conn() as conn:
            cur = conn.execute("INSERT INTO users (name, role) VALUES (?, 'admin')", (name,))
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        sys.exit(f"User '{name}' already exists.")
    print("Admin created. This key is shown ONCE, copy it now:")
    print(create_key_for(user_id, "bootstrap"))


def set_password(name: str) -> None:
    init_db()
    password = secrets.token_urlsafe(12)
    with get_conn() as conn:
        cur = conn.execute("UPDATE users SET password_hash = ? WHERE name = ?",
                           (hash_password(password), name))
    if cur.rowcount == 0:
        sys.exit(f"No such user '{name}'.")
    print("New password, shown ONCE:", file=sys.stderr)
    print(password)


COMMANDS = {"create-admin": create_admin, "set-password": set_password}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in COMMANDS:
        sys.exit("usage: python manage.py (create-admin|set-password) <name>")
    COMMANDS[sys.argv[1]](sys.argv[2])
