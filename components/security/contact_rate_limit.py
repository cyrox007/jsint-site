from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import time
import unicodedata
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

import redis
from flask import request, session

from cache.redis import redis_client
from settings import config

logger = logging.getLogger(__name__)

_SESSION_KEY = "_contact_challenge"
_HONEYPOTS = ("website", "company_site", "fax_number")
_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>{}\[\]]+")
_REPEAT_RE = re.compile(r"(.)\1{39,}", re.DOTALL)
_TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class ContactSpamGuard:
    PREFIX = "jsint:public:contact"

    @staticmethod
    def _digest(value: str) -> str:
        secret = config.SECRET_KEY.encode("utf-8")
        return hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()

    @classmethod
    def _ip_digest(cls) -> str:
        return cls._digest(request.remote_addr or "unknown")

    @classmethod
    def _counter_key(cls, suffix: str) -> str:
        return f"{cls.PREFIX}:{suffix}"

    @staticmethod
    def _read_int(key: str) -> int:
        current = redis_client.get(key)
        try:
            return int(current or "0")
        except ValueError:
            return 0

    @classmethod
    def issue_challenge(cls) -> str:
        nonce = secrets.token_urlsafe(24)
        session[_SESSION_KEY] = {
            "nonce": nonce,
            "issued_at": int(time.time()),
        }
        return nonce

    @classmethod
    def consume_challenge(cls, submitted: str) -> bool:
        challenge = session.pop(_SESSION_KEY, None)
        if not isinstance(challenge, dict):
            return False

        expected = challenge.get("nonce")
        issued_at = challenge.get("issued_at")
        if not isinstance(expected, str) or not isinstance(issued_at, int):
            return False
        if not submitted or not hmac.compare_digest(expected, submitted):
            return False

        age = int(time.time()) - issued_at
        return config.CONTACT_FORM_MIN_SECONDS <= age <= config.CONTACT_FORM_TTL_SECONDS

    @staticmethod
    def honeypot_triggered() -> bool:
        return any(request.form.get(name, "").strip() for name in _HONEYPOTS)

    @classmethod
    def volume_blocked(cls) -> bool:
        ip_digest = cls._ip_digest()
        checks = (
            (
                cls._counter_key(f"ip:short:{ip_digest}"),
                config.CONTACT_RATE_LIMIT_ATTEMPTS,
            ),
            (
                cls._counter_key(f"ip:daily:{ip_digest}"),
                config.CONTACT_DAILY_LIMIT_ATTEMPTS,
            ),
            (
                cls._counter_key("global"),
                config.CONTACT_GLOBAL_LIMIT_ATTEMPTS,
            ),
        )
        try:
            return any(cls._read_int(key) >= limit for key, limit in checks)
        except redis.RedisError as exc:
            cls._redis_failure(exc)
            return True

    @classmethod
    def record_attempt(cls) -> None:
        ip_digest = cls._ip_digest()
        try:
            redis_client.increment_with_expiry(
                cls._counter_key(f"ip:short:{ip_digest}"),
                config.CONTACT_RATE_LIMIT_WINDOW_SECONDS,
            )
            redis_client.increment_with_expiry(
                cls._counter_key(f"ip:daily:{ip_digest}"),
                config.CONTACT_DAILY_LIMIT_WINDOW_SECONDS,
            )
            redis_client.increment_with_expiry(
                cls._counter_key("global"),
                config.CONTACT_GLOBAL_LIMIT_WINDOW_SECONDS,
            )
        except redis.RedisError as exc:
            cls._redis_failure(exc)

    @classmethod
    def reply_blocked(cls, reply_to: str) -> bool:
        key = cls._counter_key(f"reply:{cls._digest(reply_to.casefold())}")
        try:
            return cls._read_int(key) >= config.CONTACT_REPLY_LIMIT_ATTEMPTS
        except redis.RedisError as exc:
            cls._redis_failure(exc)
            return True

    @classmethod
    def record_reply(cls, reply_to: str) -> None:
        key = cls._counter_key(f"reply:{cls._digest(reply_to.casefold())}")
        try:
            redis_client.increment_with_expiry(
                key,
                config.CONTACT_DAILY_LIMIT_WINDOW_SECONDS,
            )
        except redis.RedisError as exc:
            cls._redis_failure(exc)

    @classmethod
    def fingerprint(cls, values: dict[str, str]) -> str:
        normalized = "\n".join(
            (
                values["reply_to"].casefold(),
                values["subject"].casefold(),
                values["message"].casefold(),
            )
        )
        return cls._digest(normalized)

    @classmethod
    def storage_fingerprint(cls, fingerprint: str) -> str:
        bucket = int(time.time()) // config.CONTACT_DUPLICATE_WINDOW_SECONDS
        return cls._digest(f"{fingerprint}:{bucket}")

    @classmethod
    def reserve_fingerprint(cls, fingerprint: str) -> bool:
        key = cls._counter_key(f"duplicate:{fingerprint}")
        try:
            return redis_client.set_if_absent(
                key,
                "1",
                config.CONTACT_DUPLICATE_WINDOW_SECONDS,
            )
        except redis.RedisError as exc:
            cls._redis_failure(exc)
            return False

    @classmethod
    def release_fingerprint(cls, fingerprint: str) -> None:
        try:
            redis_client.delete(cls._counter_key(f"duplicate:{fingerprint}"))
        except redis.RedisError:
            pass

    @staticmethod
    def content_errors(values: dict[str, str]) -> list[str]:
        errors: list[str] = []
        combined = "\n".join((values["subject"], values["message"]))

        if len(_URL_RE.findall(combined)) > config.CONTACT_MAX_URLS:
            errors.append("В сообщении слишком много ссылок.")

        if _REPEAT_RE.search(combined):
            errors.append("Сообщение содержит слишком длинную повторяющуюся последовательность.")

        if combined.count("\n") > 80:
            errors.append("Сообщение содержит слишком много строк.")

        letters_or_digits = sum(char.isalnum() for char in values["message"])
        if letters_or_digits < 10:
            errors.append("Сообщение содержит недостаточно осмысленного текста.")

        hidden_controls = sum(
            1
            for char in combined
            if unicodedata.category(char) == "Cf"
        )
        if hidden_controls > 2:
            errors.append("Сообщение содержит недопустимые скрытые символы.")

        return errors

    @staticmethod
    def turnstile_enabled() -> bool:
        return bool(
            config.CONTACT_TURNSTILE_SITE_KEY
            and config.CONTACT_TURNSTILE_SECRET_KEY
        )

    @classmethod
    def verify_turnstile(cls, token: str) -> bool:
        if not cls.turnstile_enabled():
            return not config.CONTACT_TURNSTILE_REQUIRED

        token = token.strip()
        if not token or len(token) > 2048:
            return False

        body = urlencode(
            {
                "secret": config.CONTACT_TURNSTILE_SECRET_KEY,
                "response": token,
                "idempotency_key": str(uuid4()),
            }
        ).encode("utf-8")
        verification = Request(
            _TURNSTILE_VERIFY_URL,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "jsint-site-contact/1.0",
            },
            method="POST",
        )

        try:
            with urlopen(verification, timeout=4) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Проверка Turnstile недоступна: %s", type(exc).__name__)
            return False

        if payload.get("success") is not True:
            return False
        if payload.get("action") not in {None, "", "contact"}:
            return False

        hostname = str(payload.get("hostname") or "").lower()
        expected_host = request.host.split(":", 1)[0].lower()
        return not hostname or hostname == expected_host

    @staticmethod
    def _redis_failure(exc: redis.RedisError) -> None:
        logger.error("Redis недоступен для защиты формы обратной связи: %s", exc)
        if config.REDIS_REQUIRED:
            raise RuntimeError("Сервис защиты формы временно недоступен") from exc
