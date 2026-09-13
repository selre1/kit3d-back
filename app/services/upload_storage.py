"""업로드 원본 파일의 저장/조회 공통 처리.

IFC(import_job_service)와 FBX(import_job_fbx_service)가 함께 쓴다.
포맷별 업무 로직은 각 서비스에 두고, 여기에는 파일 입출력만 둔다.
"""

import os
import shutil
import zipfile
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile


def get_assets_root() -> Path:
    return Path(os.getenv("ASSETS_DIR", "/data/assets"))


class DuplicateFileNameError(Exception):
    pass


class InvalidArchiveError(Exception):
    pass


class UploadFileMissingError(Exception):
    pass


class UploadFileAccessError(Exception):
    pass


def normalize_file_format(value: str | None) -> str | None:
    """'.IFC', 'ifc ' 같은 값을 점 없는 소문자로 정리한다."""
    text = str(value or "").strip().lower().lstrip(".")
    return text or None


def resolve_file_format(file_name: str) -> str | None:
    """파일명 확장자에서 저장용 file_format 값을 만든다."""
    return normalize_file_format(Path(file_name).suffix)


def save_upload_file(
    project_id: UUID,
    upload: UploadFile,
    file_format: str,
) -> tuple[str, str, int | None]:
    """원본을 assets/model/{project_id}/{file_format}/ 아래에 저장한다."""
    project_rel_dir = Path("model") / str(project_id) / file_format
    project_dir = get_assets_root() / project_rel_dir
    project_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(upload.filename or f"upload.{file_format}").name
    dest_path = project_dir / filename

    relative_path = (project_rel_dir / filename).as_posix()
    file_url = f"/assets/{relative_path}"

    size = 0
    try:
        with open(dest_path, "xb") as out_file:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                out_file.write(chunk)
                size += len(chunk)
    except FileExistsError as exc:
        raise DuplicateFileNameError() from exc

    return str(dest_path), str(file_url), size


def resolve_stored_path(file_path: str | None) -> str:
    """DB에 기록된 경로가 assets 루트 안의 실제 파일인지 확인하고 절대경로를 돌려준다."""
    if not file_path:
        raise UploadFileMissingError()

    upload_root = get_assets_root().resolve()
    resolved_path = Path(file_path).resolve()
    if resolved_path != upload_root and upload_root not in resolved_path.parents:
        raise UploadFileAccessError()

    if not resolved_path.is_file():
        raise UploadFileMissingError()

    return str(resolved_path)


def close_uploads(files: list[UploadFile]) -> None:
    for upload in files:
        try:
            upload.file.close()
        except Exception:
            pass


def list_archive_names(upload: UploadFile) -> list[str]:
    """zip 안에 든 파일 경로 목록."""
    upload.file.seek(0)
    try:
        archive = zipfile.ZipFile(upload.file)
    except zipfile.BadZipFile as exc:
        raise InvalidArchiveError() from exc

    with archive:
        return [info.filename for info in archive.infolist() if not info.is_dir()]


def extract_archive(upload: UploadFile, project_id: UUID, file_format: str) -> dict[str, int]:
    """zip 을 assets/model/{project_id}/{file_format}/ 아래에 구조 그대로 푼다.

    {zip 안의 경로: 저장된 크기} 를 돌려준다.
    """
    dest_root = (get_assets_root() / "model" / str(project_id) / file_format).resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    upload.file.seek(0)
    try:
        archive = zipfile.ZipFile(upload.file)
    except zipfile.BadZipFile as exc:
        raise InvalidArchiveError() from exc

    written: dict[str, int] = {}
    with archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        if len(infos) > 2000:
            raise InvalidArchiveError()
        if sum(info.file_size for info in infos) > 2 * 1024 * 1024 * 1024:
            raise InvalidArchiveError()

        # 한 건이라도 폴더 밖을 가리키면 아무것도 쓰지 않는다.
        targets = []
        for info in infos:
            target = (dest_root / info.filename).resolve()
            if dest_root != target.parent and dest_root not in target.parents:
                raise InvalidArchiveError()
            targets.append((info, target))

        for info, target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, open(target, "wb") as out_file:
                shutil.copyfileobj(source, out_file, 1024 * 1024)
            written[info.filename] = target.stat().st_size

    return written
