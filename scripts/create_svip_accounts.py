"""Create three SVIP accounts and print their one-time initial passwords.

Run from the project root:
    python scripts/create_svip_accounts.py

Passwords are generated locally and are never written to source control.
Existing accounts are retained and are not reset.
"""
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth import create_user, init_auth_db  # noqa: E402
from storage import DB_PATH, get_connection  # noqa: E402


def main():
    init_auth_db()
    print("Crypto Radar AI · SVIP account bootstrap")
    print(f"Database: {DB_PATH}")
    print("Save these passwords now. They will not be shown again.\n")

    for index in range(1, 4):
        username = f"svip{index:02d}"
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id, role FROM users WHERE username = ?",
                (username,),
            ).fetchone()

        if existing:
            with get_connection() as conn:
                conn.execute("UPDATE users SET role = 'svip' WHERE username = ?", (username,))
            print(f"{username}: already exists; role confirmed as SVIP; password unchanged")
            continue

        password = secrets.token_urlsafe(18)
        create_user(username, password, role="svip")
        print(f"Username: {username}")
        print(f"Password: {password}")
        print("-" * 48)

    print("\nDone. Keep the passwords in a password manager; do not commit them to Git.")


if __name__ == "__main__":
    main()
