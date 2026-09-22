from __future__ import annotations

# Публичные Ed25519 trust roots Workspace Organizer.
# Здесь допустимы только PUBLIC keys. Соответствующие private keys остаются офлайн
# и никогда не должны попадать на web-сервер, в БД, CI или release artifacts.
LICENSE_TRUSTED_KEYS = {
    "prod-license-2026-01": "IeudHzvZ-NemtyhPrbs8OsqDiieInl4MO4meFmqfel4",
}

UPDATE_TRUSTED_KEYS = {
    "update-prod-2026-01": "HFDLlfhevvFZQRlA-ZVZLnmpH1U5bcG8SJMw2uZOXL8",
}
