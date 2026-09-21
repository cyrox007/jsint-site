from __future__ import annotations

from flask import jsonify
from sqlalchemy import text

from cache.redis import redis_client
from database import Database
from settings import config


def healthcheck():
    checks = {"database": False, "redis": False}

    session = None
    try:
        session = Database.connect_database()
        session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False
    finally:
        if session is not None:
            session.close()

    checks["redis"] = redis_client.ping()

    critical_ok = checks["database"] and (checks["redis"] or not config.REDIS_REQUIRED)
    status = (
        "ok"
        if critical_ok and checks["redis"]
        else ("degraded" if critical_ok else "error")
    )

    return jsonify({"status": status, "checks": checks}), (200 if critical_ok else 503)
