from __future__ import annotations

import json
import time
from typing import Any

import redis

from cache.redis import redis_client
from version import application_version

BACKGROUND_HEARTBEAT_KEY = "jsint:background:heartbeat"
BACKGROUND_HEARTBEAT_TTL = 120


def record_background_heartbeat() -> dict[str, Any]:
    payload = {
        "timestamp": time.time(),
        "version": application_version(),
    }
    redis_client.set(
        BACKGROUND_HEARTBEAT_KEY,
        json.dumps(payload, ensure_ascii=False),
        ex=BACKGROUND_HEARTBEAT_TTL,
    )
    return payload


def get_background_status() -> dict[str, Any]:
    try:
        raw = redis_client.get(BACKGROUND_HEARTBEAT_KEY)
    except redis.RedisError:
        return {
            "ok": False,
            "reason": "redis_unavailable",
            "version": None,
            "age_seconds": None,
        }

    if not raw:
        return {
            "ok": False,
            "reason": "heartbeat_missing",
            "version": None,
            "age_seconds": None,
        }

    try:
        payload = json.loads(raw)
        timestamp = float(payload["timestamp"])
        version = str(payload.get("version") or "")
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return {
            "ok": False,
            "reason": "heartbeat_invalid",
            "version": None,
            "age_seconds": None,
        }

    age = max(0.0, time.time() - timestamp)
    ok = age <= BACKGROUND_HEARTBEAT_TTL
    return {
        "ok": ok,
        "reason": "ok" if ok else "heartbeat_stale",
        "version": version or None,
        "age_seconds": round(age, 1),
    }
