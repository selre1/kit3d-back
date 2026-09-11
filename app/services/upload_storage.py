"""업로드 원본 파일의 저장/조회 공통 처리.

IFC(import_job_service)와 FBX(import_job_fbx_service)가 함께 쓴다.
포맷별 업무 로직은 각 서비스에 두고, 여기에는 파일 입출력만 둔다.
"""

import os
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile


class DuplicateFileNameError(Exception):
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
    upload_root = Path(os.getenv("ASSETS_DIR", "assets"))
    project_rel_dir = Path("model") / str(project_id) / file_format
    project_dir = upload_root / project_rel_dir
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

    upload_root = Path(os.getenv("ASSETS_DIR", "assets")).resolve()
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
