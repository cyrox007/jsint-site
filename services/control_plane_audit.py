from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import String, func, or_
from sqlalchemy.orm import Session

from models.control_plane import ControlPlaneAuditRecord, LicenseRecord, ReleaseRecord
from models.users import User
from settings import config


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_details(details: dict[str, Any] | None) -> dict[str, Any]:
    if not details:
        return {}

    result: dict[str, Any] = {}
    blocked = {"token", "credential", "activation_code", "private_key", "secret"}
    for key, value in details.items():
        normalized = str(key).strip()[:80]
        if not normalized or normalized.lower() in blocked:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[normalized] = value if not isinstance(value, str) else value[:500]
    return result


class ControlPlaneAuditService:
    @staticmethod
    def record(
        session: Session,
        *,
        actor_kind: str,
        action: str,
        outcome: str = "success",
        actor_user_id: UUID | None = None,
        actor_label: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        installation_id: UUID | None = None,
        license_id: str | None = None,
        release_id: UUID | None = None,
        details: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> ControlPlaneAuditRecord:
        record = ControlPlaneAuditRecord(
            actor_kind=actor_kind[:16],
            actor_user_id=actor_user_id,
            actor_label=actor_label[:320] if actor_label else None,
            action=action[:96],
            outcome=outcome[:16],
            target_type=target_type[:48] if target_type else None,
            target_id=target_id[:160] if target_id else None,
            installation_id=installation_id,
            license_id=license_id[:128] if license_id else None,
            release_id=release_id,
            details=_safe_details(details),
        )
        session.add(record)
        if commit:
            session.commit()
            session.refresh(record)
        return record

    @staticmethod
    def operator(
        session: Session,
        *,
        actor_user_id: UUID | None,
        action: str,
        target_type: str,
        target_id: str,
        installation_id: UUID | None = None,
        license_id: str | None = None,
        release_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> ControlPlaneAuditRecord:
        actor_label = None
        if actor_user_id is not None:
            user = session.query(User).filter(User.id == actor_user_id).first()
            if user is not None:
                actor_label = user.email

        return ControlPlaneAuditService.record(
            session,
            actor_kind="operator",
            actor_user_id=actor_user_id,
            actor_label=actor_label,
            action=action,
            target_type=target_type,
            target_id=target_id,
            installation_id=installation_id,
            license_id=license_id,
            release_id=release_id,
            details=details,
        )

    @staticmethod
    def machine_failure(
        session: Session,
        *,
        action: str,
        installation_id: UUID | None,
        target_id: str | None,
        error_code: str,
        http_status: int,
    ) -> None:
        ControlPlaneAuditService.record(
            session,
            actor_kind="machine",
            action=action,
            outcome="failure",
            target_type="artifact",
            target_id=target_id,
            installation_id=installation_id,
            details={
                "error_code": error_code,
                "http_status": http_status,
            },
        )

    @staticmethod
    def list_records(
        session: Session,
        *,
        action: str | None = None,
        outcome: str | None = None,
        query: str | None = None,
        limit: int = 200,
    ) -> list[ControlPlaneAuditRecord]:
        stmt = session.query(ControlPlaneAuditRecord)
        if action:
            stmt = stmt.filter(ControlPlaneAuditRecord.action == action)
        if outcome in {"success", "failure"}:
            stmt = stmt.filter(ControlPlaneAuditRecord.outcome == outcome)
        if query:
            needle = f"%{query.strip()[:160]}%"
            stmt = stmt.filter(
                or_(
                    ControlPlaneAuditRecord.target_id.ilike(needle),
                    ControlPlaneAuditRecord.license_id.ilike(needle),
                    func.cast(ControlPlaneAuditRecord.installation_id, String).ilike(needle),
                )
            )
        return (
            stmt.order_by(ControlPlaneAuditRecord.created_at.desc())
            .limit(max(1, min(limit, 500)))
            .all()
        )

    @staticmethod
    def dashboard(session: Session) -> dict[str, Any]:
        now = _now()
        online_after = now - timedelta(minutes=15)
        expiring_before = now + timedelta(days=30)
        event_after = now - timedelta(hours=24)

        active_installations = (
            session.query(LicenseRecord)
            .filter(
                LicenseRecord.status == "active",
                LicenseRecord.last_seen_at.is_not(None),
                LicenseRecord.last_seen_at >= online_after,
            )
            .count()
        )
        expiring_licenses = (
            session.query(LicenseRecord)
            .filter(
                LicenseRecord.status == "active",
                LicenseRecord.updates_until.is_not(None),
                LicenseRecord.updates_until > now,
                LicenseRecord.updates_until <= expiring_before,
            )
            .count()
        )
        artifact_errors = (
            session.query(ControlPlaneAuditRecord)
            .filter(
                ControlPlaneAuditRecord.actor_kind == "machine",
                ControlPlaneAuditRecord.outcome == "failure",
                ControlPlaneAuditRecord.created_at >= event_after,
            )
            .count()
        )
        denied_access = (
            session.query(ControlPlaneAuditRecord)
            .filter(
                ControlPlaneAuditRecord.actor_kind == "machine",
                ControlPlaneAuditRecord.outcome == "failure",
                ControlPlaneAuditRecord.created_at >= event_after,
                ControlPlaneAuditRecord.details["error_code"].astext == "update_access_denied",
            )
            .count()
        )
        latest_releases = (
            session.query(ReleaseRecord)
            .order_by(ReleaseRecord.published_at.desc())
            .limit(3)
            .all()
        )

        return {
            "active_installations": active_installations,
            "expiring_licenses": expiring_licenses,
            "artifact_errors_24h": artifact_errors,
            "denied_access_24h": denied_access,
            "latest_releases": latest_releases,
            "retention_days": config.OPERATOR_AUDIT_RETENTION_DAYS,
        }

    @staticmethod
    def channel_state(session: Session) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for channel in ("stable", "beta", "alpha"):
            record = (
                session.query(ReleaseRecord)
                .filter(
                    ReleaseRecord.channel == channel,
                    ReleaseRecord.is_active.is_(True),
                )
                .order_by(ReleaseRecord.version_code.desc())
                .first()
            )
            result.append({"channel": channel, "record": record})
        return result
