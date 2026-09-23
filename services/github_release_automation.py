from __future__ import annotations

import hashlib
import json
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from types import SimpleNamespace
from typing import Any, BinaryIO

from sqlalchemy.orm import Session

from models.control_plane import ReleaseRecord
from services.notes_control_plane import ControlPlaneError, NotesControlPlane
from settings import config


_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TAG_RE = re.compile(r"^v[0-9A-Za-z][0-9A-Za-z._+-]{0,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_CONST_RE = re.compile(r"public const VERSION\\s*=\\s*['\"]([^'\"]+)['\"]")
_VERSION_CODE_CONST_RE = re.compile(r"public const VERSION_CODE\\s*=\\s*([0-9]+)")
_STATUS_CONST_RE = re.compile(r"public const STATUS\\s*=\\s*['\"]([^'\"]+)['\"]")
_ALLOWED_REDIRECT_HOSTS = {
    "api.github.com",
    "github.com",
}
_MAX_SMALL_ASSET_BYTES = 4096
_MAX_VERSION_FILE_BYTES = 131072


def _allowed_github_host(host: str) -> bool:
    host = host.lower()
    return host in _ALLOWED_REDIRECT_HOSTS or host.endswith(".githubusercontent.com")


class _SafeGitHubRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme != "https" or not parsed.hostname or not _allowed_github_host(parsed.hostname):
            raise urllib.error.HTTPError(
                newurl,
                403,
                "GitHub перенаправил запрос на недоверенный адрес",
                headers,
                fp,
            )

        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None

        old_host = (urllib.parse.urlparse(req.full_url).hostname or "").lower()
        if old_host != parsed.hostname.lower():
            redirected.remove_header("Authorization")
            redirected.remove_header("authorization")
        return redirected


_OPENER = urllib.request.build_opener(_SafeGitHubRedirectHandler())


def _repository() -> str:
    repository = config.NOTES_RELEASE_GITHUB_REPOSITORY.strip()
    if _REPOSITORY_RE.fullmatch(repository) is None:
        raise ControlPlaneError(
            "Некорректный NOTES_RELEASE_GITHUB_REPOSITORY",
            status=503,
            code="release_source_misconfigured",
        )
    return repository


def _api_url(path: str) -> str:
    return "https://api.github.com" + path


def _request(url: str, *, accept: str) -> BinaryIO:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "api.github.com":
        raise ControlPlaneError(
            "Источник релиза должен использовать GitHub API",
            status=503,
            code="release_source_misconfigured",
        )

    headers = {
        "Accept": accept,
        "User-Agent": "jsint-site-release-automation/1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = config.NOTES_RELEASE_GITHUB_TOKEN.strip()
    if token:
        headers["Authorization"] = "Bearer " + token

    try:
        return _OPENER.open(
            urllib.request.Request(url, headers=headers, method="GET"),
            timeout=120,
        )
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ControlPlaneError(
                "GitHub Release или его artifact не найден",
                status=404,
                code="release_source_not_found",
            ) from exc
        raise ControlPlaneError(
            f"GitHub API вернул HTTP {exc.code}",
            status=502,
            code="release_source_unavailable",
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ControlPlaneError(
            "Не удалось связаться с GitHub для подготовки релиза",
            status=502,
            code="release_source_unavailable",
        ) from exc


def _request_json(path: str) -> dict[str, Any]:
    response = _request(_api_url(path), accept="application/vnd.github+json")
    with response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ControlPlaneError("Ответ GitHub API слишком большой", status=502)

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControlPlaneError("GitHub API вернул некорректный JSON", status=502) from exc
    if not isinstance(payload, dict):
        raise ControlPlaneError("GitHub API вернул неожиданный ответ", status=502)
    return payload


def _release(tag: str) -> dict[str, Any]:
    repository = _repository()
    encoded_repository = "/".join(urllib.parse.quote(part, safe="") for part in repository.split("/"))
    if tag:
        if _TAG_RE.fullmatch(tag) is None:
            raise ControlPlaneError("Некорректный Git tag")
        encoded_tag = urllib.parse.quote(tag, safe="")
        path = f"/repos/{encoded_repository}/releases/tags/{encoded_tag}"
    else:
        path = f"/repos/{encoded_repository}/releases/latest"

    payload = _request_json(path)
    if payload.get("draft"):
        raise ControlPlaneError("Черновик GitHub Release нельзя публиковать в update feed")
    return payload


def _asset_map(release: dict[str, Any]) -> dict[str, dict[str, Any]]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ControlPlaneError("GitHub Release не содержит список artifacts", status=502)

    result: dict[str, dict[str, Any]] = {}
    for item in assets:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str) and name:
            result[name] = item
    return result


def _asset_response(asset: dict[str, Any]) -> BinaryIO:
    api_url = asset.get("url")
    if not isinstance(api_url, str) or not api_url:
        raise ControlPlaneError("GitHub artifact не содержит API URL", status=502)
    return _request(api_url, accept="application/octet-stream")


def _read_small_asset(asset: dict[str, Any]) -> str:
    response = _asset_response(asset)
    with response:
        raw = response.read(_MAX_SMALL_ASSET_BYTES + 1)
    if len(raw) > _MAX_SMALL_ASSET_BYTES:
        raise ControlPlaneError("Служебный artifact GitHub слишком большой", status=502)
    try:
        return raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ControlPlaneError("Служебный artifact GitHub не является UTF-8", status=502) from exc


def _expected_sha256(checksum_text: str, package_name: str) -> str:
    first_line = checksum_text.splitlines()[0].strip() if checksum_text else ""
    match = re.fullmatch(r"([0-9a-f]{64})\\s+\\*?(.+)", first_line)
    if match is None:
        raise ControlPlaneError("Некорректный SHA-256 artifact GitHub", status=502)
    filename = match.group(2).strip()
    if filename != package_name:
        raise ControlPlaneError("SHA-256 artifact относится к другому ZIP", status=502)
    return match.group(1)


def _source_commit(source_text: str) -> str:
    source = source_text.strip().lower()
    if _SHA_RE.fullmatch(source) is None:
        raise ControlPlaneError("Некорректный source SHA artifact GitHub", status=502)
    return source


def _resolve_tag_commit(tag: str) -> str:
    repository = _repository()
    encoded_repository = "/".join(urllib.parse.quote(part, safe="") for part in repository.split("/"))
    encoded_tag = urllib.parse.quote(tag, safe="")
    ref = _request_json(f"/repos/{encoded_repository}/git/ref/tags/{encoded_tag}")
    obj = ref.get("object")
    if not isinstance(obj, dict):
        raise ControlPlaneError("Git tag не содержит target object", status=502)

    for _ in range(4):
        object_type = obj.get("type")
        sha = str(obj.get("sha", "")).lower()
        if _SHA_RE.fullmatch(sha) is None:
            raise ControlPlaneError("Git tag содержит некорректный SHA", status=502)
        if object_type == "commit":
            return sha
        if object_type != "tag":
            raise ControlPlaneError("Git tag указывает на неподдерживаемый object", status=502)
        tag_object = _request_json(f"/repos/{encoded_repository}/git/tags/{sha}")
        obj = tag_object.get("object")
        if not isinstance(obj, dict):
            raise ControlPlaneError("Аннотированный Git tag повреждён", status=502)

    raise ControlPlaneError("Слишком глубокая цепочка аннотированных Git tags", status=502)


def _download_package(asset: dict[str, Any], expected_sha256: str) -> tuple[BinaryIO, int, str]:
    declared_size = asset.get("size")
    if not isinstance(declared_size, int) or declared_size <= 0:
        raise ControlPlaneError("GitHub artifact не содержит корректный размер", status=502)

    if declared_size > config.NOTES_RELEASE_UPLOAD_MAX_BYTES:
        raise ControlPlaneError(
            "GitHub artifact превышает допустимый размер release storage",
            status=413,
            code="package_too_large",
        )

    digest = asset.get("digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise ControlPlaneError(
            "GitHub Release не содержит SHA-256 digest для ZIP",
            status=502,
            code="release_provenance_missing",
        )
    api_sha256 = digest.removeprefix("sha256:").lower()
    if _SHA256_RE.fullmatch(api_sha256) is None or api_sha256 != expected_sha256:
        raise ControlPlaneError("SHA-256 metadata GitHub не совпадает с checksum artifact", status=502)

    response = _asset_response(asset)
    temporary = tempfile.TemporaryFile(mode="w+b")
    hasher = hashlib.sha256()
    size = 0
    try:
        with response:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > config.NOTES_RELEASE_UPLOAD_MAX_BYTES:
                    raise ControlPlaneError(
                        "Загрузка GitHub artifact превысила допустимый размер",
                        status=413,
                        code="package_too_large",
                    )
                temporary.write(chunk)
                hasher.update(chunk)

        actual_sha256 = hasher.hexdigest()
        if size != declared_size or actual_sha256 != expected_sha256:
            raise ControlPlaneError(
                "Скачанный ZIP не совпадает с GitHub Release metadata",
                status=502,
                code="release_provenance_mismatch",
            )
        temporary.seek(0)
        return temporary, size, actual_sha256
    except Exception:
        temporary.close()
        raise


def _inspect_workspace_zip(stream: BinaryIO) -> dict[str, Any]:
    stream.seek(0)
    try:
        with zipfile.ZipFile(stream) as archive:
            candidates = [
                item
                for item in archive.infolist()
                if item.filename == "core/Version.php" or item.filename.endswith("/core/Version.php")
            ]
            if len(candidates) != 1:
                raise ControlPlaneError("В release ZIP не найден единственный core/Version.php")
            info = candidates[0]
            if info.file_size <= 0 or info.file_size > _MAX_VERSION_FILE_BYTES:
                raise ControlPlaneError("core/Version.php имеет недопустимый размер")
            source = archive.read(info).decode("utf-8")
    except (zipfile.BadZipFile, UnicodeDecodeError, OSError) as exc:
        raise ControlPlaneError("Не удалось прочитать версию из release ZIP") from exc
    finally:
        stream.seek(0)

    version_match = _VERSION_CONST_RE.search(source)
    code_match = _VERSION_CODE_CONST_RE.search(source)
    status_match = _STATUS_CONST_RE.search(source)
    if version_match is None or code_match is None or status_match is None:
        raise ControlPlaneError("core/Version.php не содержит ожидаемые константы релиза")

    version = version_match.group(1)
    version_code = int(code_match.group(1))
    status = status_match.group(1).lower()
    if status not in {"stable", "beta", "alpha"}:
        raise ControlPlaneError("Неподдерживаемый STATUS в release ZIP")
    if version_code <= 1:
        raise ControlPlaneError("version_code недостаточен для последовательного обновления")

    return {
        "version": version,
        "version_code": version_code,
        "status": status,
    }


def _sequential_source_floor(version_code: int) -> int:
    if version_code <= 1:
        raise ControlPlaneError("Нельзя вычислить предыдущий version_code")
    return version_code - 1


class GitHubReleaseAutomation:
    @classmethod
    def prepare(cls, session: Session, *, tag: str = "") -> dict[str, Any]:
        release = _release(tag.strip())
        tag_name = str(release.get("tag_name", "")).strip()
        if _TAG_RE.fullmatch(tag_name) is None:
            raise ControlPlaneError("GitHub Release содержит некорректный tag")

        package_name = f"workspace-organizer-{tag_name}.zip"
        assets = _asset_map(release)
        package_asset = assets.get(package_name)
        checksum_asset = assets.get(package_name + ".sha256")
        source_asset = assets.get(package_name + ".source-sha")
        if package_asset is None or checksum_asset is None or source_asset is None:
            raise ControlPlaneError(
                "GitHub Release должен содержать ZIP, .sha256 и .source-sha",
                status=502,
                code="release_provenance_missing",
            )

        expected_sha256 = _expected_sha256(
            _read_small_asset(checksum_asset),
            package_name,
        )
        source_commit = _source_commit(_read_small_asset(source_asset))
        tag_commit = _resolve_tag_commit(tag_name)
        if source_commit != tag_commit:
            raise ControlPlaneError(
                "Source SHA пакета не совпадает с commit Git tag",
                status=502,
                code="release_provenance_mismatch",
            )

        package_stream, package_size, package_sha256 = _download_package(
            package_asset,
            expected_sha256,
        )
        try:
            package_meta = _inspect_workspace_zip(package_stream)
            version = package_meta["version"]
            version_code = package_meta["version_code"]
            channel = package_meta["status"]

            if tag_name != "v" + version:
                raise ControlPlaneError("Версия внутри ZIP не совпадает с Git tag")
            if bool(release.get("prerelease")) != (channel != "stable"):
                raise ControlPlaneError("GitHub prerelease state не совпадает со STATUS пакета")

            existing = (
                session.query(ReleaseRecord)
                .filter(
                    ReleaseRecord.channel == channel,
                    ReleaseRecord.version_code == version_code,
                )
                .first()
            )
            if existing is not None:
                raise ControlPlaneError(
                    f"Релиз {version} ({channel}) уже зарегистрирован",
                    status=409,
                    code="release_already_registered",
                )

            stored = NotesControlPlane.store_release_upload(
                SimpleNamespace(filename=package_name, stream=package_stream)
            )
        finally:
            package_stream.close()

        if stored["size"] != package_size or stored["sha256"] != package_sha256:
            raise ControlPlaneError(
                "Release storage изменил содержимое ZIP",
                status=500,
                code="release_storage_mismatch",
            )

        min_source_version_code = _sequential_source_floor(version_code)
        manifest, resolved_path = NotesControlPlane.prepare_release_manifest(
            package_path=stored["path"],
            version=version,
            version_code=version_code,
            channel=channel,
            source_commit=source_commit,
            min_source_version_code=min_source_version_code,
            requires_php=config.NOTES_RELEASE_DEFAULT_REQUIRES_PHP,
        )

        return {
            "manifest": manifest,
            "package_path": resolved_path,
            "repository": _repository(),
            "tag": tag_name,
            "version": version,
            "version_code": version_code,
            "channel": channel,
            "source_commit": source_commit,
            "min_source_version_code": min_source_version_code,
            "requires_php": config.NOTES_RELEASE_DEFAULT_REQUIRES_PHP,
            "package_name": stored["filename"],
            "package_size": stored["size"],
            "package_sha256": stored["sha256"],
        }
