#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import re
import sys

from sqlalchemy import text

from cache.redis import redis_client
from database import Database
from models.users import User
from settings import config
from utils.hash_password import hash_password

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _read_password() -> str:
    first = getpass.getpass("Новый пароль: ")
    second = getpass.getpass("Повторите пароль: ")
    if first != second:
        raise RuntimeError("Пароли не совпадают")
    if len(first) < 12:
        raise RuntimeError("Пароль должен содержать минимум 12 символов")
    if len(first) > 1024:
        raise RuntimeError("Пароль слишком длинный")
    return first


def _email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 320 or _EMAIL_RE.fullmatch(value) is None:
        raise RuntimeError("Некорректный email")
    return value


def cmd_create_admin(args) -> int:
    email = _email(args.email)
    password = _read_password()

    db = Database.connect_database()
    try:
        if db.query(User).filter(User.email == email).first() is not None:
            raise RuntimeError("Пользователь с таким email уже существует")

        user = User(
            email=email,
            hash_password=hash_password(password),
            firstname=args.firstname.strip() or "Admin",
            lastname=args.lastname.strip() or "",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(json.dumps({"status": "created", "email": user.email, "id": str(user.id)}, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cmd_set_password(args) -> int:
    email = _email(args.email)
    password = _read_password()

    db = Database.connect_database()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise RuntimeError("Пользователь не найден")
        user.hash_password = hash_password(password)
        db.add(user)
        db.commit()
        print(json.dumps({"status": "password_updated", "email": user.email}, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cmd_health(_args) -> int:
    checks = {"config": False, "database": False, "redis": False}

    config.validate()
    checks["config"] = True

    db = Database.connect_database()
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    finally:
        db.close()

    checks["redis"] = redis_client.ping()
    ok = checks["config"] and checks["database"] and (checks["redis"] or not config.REDIS_REQUIRED)
    print(json.dumps({"status": "ok" if ok else "error", "checks": checks}, ensure_ascii=False))
    return 0 if ok else 3


def main() -> int:
    parser = argparse.ArgumentParser(description="Операторские команды jsint-site")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-admin", help="Создать администратора")
    create.add_argument("--email", required=True)
    create.add_argument("--firstname", default="Admin")
    create.add_argument("--lastname", default="")
    create.set_defaults(handler=cmd_create_admin)

    passwd = sub.add_parser("set-password", help="Сменить пароль администратора")
    passwd.add_argument("--email", required=True)
    passwd.set_defaults(handler=cmd_set_password)

    health = sub.add_parser("health", help="Проверить production-зависимости")
    health.set_defaults(handler=cmd_health)

    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except Exception as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
