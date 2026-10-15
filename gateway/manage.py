import sqlite3
import sys

from auth import create_key_for
from db import get_conn, init_db


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] != "create-admin":
        sys.exit("usage: python manage.py create-admin <name>")
    init_db()
    try:
        with get_conn() as conn:
            cur = conn.execute("INSERT INTO users (name, role) VALUES (?, 'admin')", (sys.argv[2],))
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        sys.exit(f"User '{sys.argv[2]}' already exists.")
    key = create_key_for(user_id, "bootstrap")
    print("Admin created. This key is shown ONCE, copy it now:")
    print(key)


if __name__ == "__main__":
    main()
