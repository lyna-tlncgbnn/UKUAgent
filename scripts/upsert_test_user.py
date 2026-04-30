#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


AUTH_STORE_VERSION = 1
MIN_PASSWORD_LENGTH = 8


@dataclass(slots=True)
class UserInput:
    email: str
    password: str
    name: str
    wecom_userid: str | None
    role: str = "member"
    status: str = "active"


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sqlite_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_user(user: UserInput) -> UserInput:
    email = normalize_email(user.email)
    name = user.name.strip()
    wecom_userid = user.wecom_userid.strip() if user.wecom_userid else None
    role = user.role.strip().lower()
    status = user.status.strip().lower()

    if not email:
        raise ValueError("email is required")
    if not name:
        raise ValueError(f"name is required for {email}")
    if len(user.password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password for {email} must be at least {MIN_PASSWORD_LENGTH} characters")
    if role not in {"admin", "member"}:
        raise ValueError(f"role for {email} must be admin or member")
    if status not in {"active", "disabled"}:
        raise ValueError(f"status for {email} must be active or disabled")

    return UserInput(
        email=email,
        password=user.password,
        name=name,
        wecom_userid=wecom_userid,
        role=role,
        status=status,
    )


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1, dklen=64)
    return f"scrypt:{salt}:{digest.hex()}"


def resolve_auth_store_path(project_root: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    if os.environ.get("DEER_FLOW_AUTH_STORE_PATH"):
        return Path(os.environ["DEER_FLOW_AUTH_STORE_PATH"]).expanduser().resolve()
    if os.environ.get("DEER_FLOW_HOME"):
        return Path(os.environ["DEER_FLOW_HOME"]).expanduser().resolve() / "auth" / "users.json"
    return project_root / "backend" / ".deer-flow" / "auth" / "users.json"


def read_auth_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": AUTH_STORE_VERSION, "users": []}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("users"), list):
        raise ValueError(f"Invalid auth store: {path}")
    payload["version"] = AUTH_STORE_VERSION
    return payload


def write_auth_store(path: Path, store: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(store, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def upsert_auth_user(store: dict[str, Any], user: UserInput) -> tuple[str, bool]:
    users = store.setdefault("users", [])
    now = utc_iso()
    for record in users:
        if record.get("email") == user.email:
            record["name"] = user.name
            record["passwordHash"] = hash_password(user.password)
            record["role"] = user.role
            record["status"] = user.status
            record["updatedAt"] = now
            return str(record["id"]), False

    user_id = secrets.token_hex(12)
    users.append(
        {
            "id": user_id,
            "email": user.email,
            "name": user.name,
            "passwordHash": hash_password(user.password),
            "role": user.role,
            "status": user.status,
            "createdAt": now,
            "updatedAt": now,
        }
    )
    return user_id, True


def ensure_business_schema(conn: sqlite3.Connection) -> None:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "users" not in tables:
        conn.execute(
            """
            CREATE TABLE users (
              id VARCHAR(64) NOT NULL PRIMARY KEY,
              email VARCHAR(320) UNIQUE,
              name VARCHAR(255) NOT NULL,
              role VARCHAR(6) NOT NULL,
              status VARCHAR(8) NOT NULL,
              created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
              updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
              wecom_userid VARCHAR(255)
            )
            """
        )

    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    if "wecom_userid" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN wecom_userid VARCHAR(255)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_wecom_userid_unique ON users (wecom_userid)")


def upsert_business_user(conn: sqlite3.Connection, user_id: str, user: UserInput) -> bool:
    role = user.role.upper()
    status = user.status.upper()
    now = sqlite_now()

    existing_by_wecom = None
    if user.wecom_userid:
        existing_by_wecom = conn.execute(
            "SELECT id, email FROM users WHERE wecom_userid = ? AND id != ?",
            (user.wecom_userid, user_id),
        ).fetchone()
    if existing_by_wecom is not None:
        raise ValueError(
            f"WeCom ID {user.wecom_userid} is already bound to business user "
            f"{existing_by_wecom[0]} ({existing_by_wecom[1]})"
        )

    existing_by_email = conn.execute("SELECT id FROM users WHERE email = ? AND id != ?", (user.email, user_id)).fetchone()
    if existing_by_email is not None:
        raise ValueError(
            f"Email {user.email} already exists in business.db with a different user id: {existing_by_email[0]}"
        )

    existing = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if existing is None:
        conn.execute(
            """
            INSERT INTO users (id, email, name, role, status, wecom_userid, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, user.email, user.name, role, status, user.wecom_userid, now, now),
        )
        return True

    conn.execute(
        """
        UPDATE users
        SET email = ?, name = ?, role = ?, status = ?, wecom_userid = ?, updated_at = ?
        WHERE id = ?
        """,
        (user.email, user.name, role, status, user.wecom_userid, now, user_id),
    )
    return False


def load_batch(path: Path) -> list[UserInput]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("batch JSON must be an array")
    users: list[UserInput] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each batch item must be an object")
        users.append(
            UserInput(
                email=str(item.get("email", "")),
                password=str(item.get("password", "")),
                name=str(item.get("name", "")),
                wecom_userid=str(item["wecom_userid"]) if item.get("wecom_userid") is not None else None,
                role=str(item.get("role", "member")),
                status=str(item.get("status", "active")),
            )
        )
    return users


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or update a local login user and bind a WeCom user ID for testing.",
    )
    parser.add_argument("--email", help="Login email.")
    parser.add_argument("--password", help="Login password, at least 8 characters.")
    parser.add_argument("--name", help="Display name.")
    parser.add_argument("--wecom-userid", help="Enterprise WeChat member ID / employee number.")
    parser.add_argument("--role", choices=["admin", "member"], default="member")
    parser.add_argument("--status", choices=["active", "disabled"], default="active")
    parser.add_argument("--batch-json", help="Path to a JSON array of users.")
    parser.add_argument("--auth-store", help="Override auth users.json path.")
    parser.add_argument("--business-db", help="Override business.db path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    auth_store_path = resolve_auth_store_path(project_root, args.auth_store)
    business_db_path = Path(args.business_db).expanduser().resolve() if args.business_db else project_root / "backend" / ".deer-flow" / "business.db"

    if args.batch_json:
        users = load_batch(Path(args.batch_json).expanduser().resolve())
    else:
        missing = [key for key in ("email", "password", "name") if not getattr(args, key)]
        if missing:
            raise SystemExit(f"Missing required arguments: {', '.join('--' + key.replace('_', '-') for key in missing)}")
        users = [
            UserInput(
                email=args.email,
                password=args.password,
                name=args.name,
                wecom_userid=args.wecom_userid,
                role=args.role,
                status=args.status,
            )
        ]

    users = [validate_user(user) for user in users]
    store = read_auth_store(auth_store_path)
    business_db_path.parent.mkdir(parents=True, exist_ok=True)

    results: list[tuple[UserInput, str, bool, bool]] = []
    with sqlite3.connect(business_db_path) as conn:
        ensure_business_schema(conn)
        for user in users:
            user_id, auth_created = upsert_auth_user(store, user)
            business_created = upsert_business_user(conn, user_id, user)
            results.append((user, user_id, auth_created, business_created))
        conn.commit()

    write_auth_store(auth_store_path, store)

    print(f"Auth store: {auth_store_path}")
    print(f"Business DB: {business_db_path}")
    for user, user_id, auth_created, business_created in results:
        auth_action = "created" if auth_created else "updated"
        business_action = "created" if business_created else "updated"
        print(
            f"{user.email} -> user_id={user_id}, wecom_userid={user.wecom_userid or '-'}, "
            f"auth={auth_action}, business={business_action}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
