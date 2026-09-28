from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from werkzeug.datastructures import FileStorage

from models.media import MediaAsset
from models.site import Site
from settings import config


IMAGE_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def _detect_image_type(data: bytes) -> tuple[str, str] | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg", IMAGE_TYPES["jpg"]
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", IMAGE_TYPES["png"]
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif", IMAGE_TYPES["gif"]
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", IMAGE_TYPES["webp"]
    return None


class MediaService:
    @staticmethod
    def storage_root() -> Path:
        root = Path(config.MEDIA_STORAGE_PATH).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    @classmethod
    def absolute_path(cls, asset: MediaAsset) -> Path:
        root = cls.storage_root()
        path = (root / asset.storage_key).resolve()
        if root not in path.parents:
            raise RuntimeError("Некорректный путь медиахранилища")
        return path

    @staticmethod
    def list_for_site(session: Session, site_id: UUID) -> list[MediaAsset]:
        return (
            session.query(MediaAsset)
            .join(MediaAsset.sites)
            .filter(Site.id == site_id)
            .order_by(MediaAsset.created_at.desc())
            .all()
        )

    @staticmethod
    def get(session: Session, asset_id: UUID) -> MediaAsset | None:
        return session.query(MediaAsset).filter(MediaAsset.id == asset_id).first()

    @classmethod
    def get_public(cls, session: Session, asset_id: UUID) -> MediaAsset | None:
        asset = cls.get(session, asset_id)
        if asset is None or not asset.is_public:
            return None
        if not any(site.is_active for site in asset.sites):
            return None
        return asset

    @classmethod
    def upload_image(
        cls,
        session: Session,
        *,
        site: Site,
        upload: FileStorage,
        created_by: UUID | None,
        alt_text: str,
    ) -> MediaAsset:
        original_name = Path(upload.filename or "").name.strip()
        if not original_name:
            raise ValueError("Выберите изображение")

        data = upload.stream.read(config.MEDIA_UPLOAD_MAX_BYTES + 1)
        if not data:
            raise ValueError("Загружен пустой файл")
        if len(data) > config.MEDIA_UPLOAD_MAX_BYTES:
            raise ValueError(
                f"Изображение превышает лимит {config.MEDIA_UPLOAD_MAX_BYTES // (1024 * 1024)} МБ"
            )

        detected = _detect_image_type(data)
        if detected is None:
            raise ValueError("Разрешены только JPEG, PNG, GIF и WebP")
        extension, mime_type = detected

        digest = hashlib.sha256(data).hexdigest()
        existing = (
            session.query(MediaAsset)
            .filter(
                MediaAsset.sha256 == digest,
                MediaAsset.size_bytes == len(data),
                MediaAsset.mime_type == mime_type,
            )
            .first()
        )
        if existing is not None:
            if all(linked.id != site.id for linked in existing.sites):
                existing.sites.append(site)
            if alt_text.strip() and not existing.alt_text:
                existing.alt_text = alt_text.strip()[:500]
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        asset_id = uuid4()
        storage_key = f"{digest[:2]}/{asset_id.hex}.{extension}"
        asset = MediaAsset(
            id=asset_id,
            owner_site_id=site.id,
            storage_key=storage_key,
            original_name=original_name[:255],
            extension=extension,
            mime_type=mime_type,
            size_bytes=len(data),
            sha256=digest,
            alt_text=alt_text.strip()[:500] or None,
            is_public=True,
            created_by=created_by,
        )
        asset.sites.append(site)

        target = cls.storage_root() / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        try:
            session.add(asset)
            session.commit()
            session.refresh(asset)
        except Exception:
            session.rollback()
            target.unlink(missing_ok=True)
            raise
        return asset

    @classmethod
    def update_asset(
        cls,
        session: Session,
        *,
        asset: MediaAsset,
        site_ids: list[UUID],
        alt_text: str,
    ) -> MediaAsset:
        unique_ids = list(dict.fromkeys(site_ids))
        if not unique_ids:
            raise ValueError("Медиафайл должен быть привязан хотя бы к одному сайту")

        sites = (
            session.query(Site)
            .filter(Site.id.in_(unique_ids))
            .order_by(Site.name.asc())
            .all()
        )
        if len(sites) != len(unique_ids):
            raise ValueError("Один из выбранных сайтов не найден")

        asset.sites = sites
        if asset.owner_site_id not in {site.id for site in sites}:
            asset.owner_site_id = sites[0].id
        asset.alt_text = alt_text.strip()[:500] or None
        session.add(asset)
        session.commit()
        session.refresh(asset)
        return asset

    @classmethod
    def detach_or_delete(
        cls,
        session: Session,
        *,
        asset: MediaAsset,
        site_id: UUID,
    ) -> bool:
        site = next((item for item in asset.sites if item.id == site_id), None)
        if site is None:
            return False

        asset.sites.remove(site)
        remaining = [item for item in asset.sites if item.id != site_id]
        if remaining:
            if asset.owner_site_id == site_id:
                asset.owner_site_id = remaining[0].id
            session.add(asset)
            session.commit()
            return True

        path = cls.absolute_path(asset)
        session.delete(asset)
        session.commit()
        path.unlink(missing_ok=True)
        return True

    @staticmethod
    def public_filename(asset: MediaAsset) -> str:
        return f"image-{asset.id}.{asset.extension}"
