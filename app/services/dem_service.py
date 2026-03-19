import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.repositories.dem_repository import DuplicateDemPathError, create_dem, list_dems


class InvalidDemFileTypeError(Exception):
    pass


class DuplicateDemFileNameError(Exception):
    pass


class DemFileSaveError(Exception):
    pass


def _remove_file_safely(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def _extract_dem_filename(upload: UploadFile) -> str:
    filename = Path(upload.filename or "").name
    ext = Path(filename).suffix.lower()
    if not filename or ext not in {".tif", ".tiff"}:
        raise InvalidDemFileTypeError()
    return filename


def _resolve_dem_paths(filename: str) -> tuple[Path, str]:
    upload_root = Path(os.getenv("ASSETS_DIR", "/data/assets"))
    file_rel_path = (Path("dem") / "tif" / filename).as_posix()
    dest_path = upload_root / file_rel_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    return dest_path, file_rel_path


def _write_upload_file(upload: UploadFile, dest_path: Path) -> int:
    size = 0
    with open(dest_path, "xb") as out_file:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            out_file.write(chunk)
            size += len(chunk)
    return size


def save_dem_file(upload: UploadFile) -> dict:
    filename = _extract_dem_filename(upload)
    dest_path, file_rel_path = _resolve_dem_paths(filename)

    if dest_path.exists():
        raise DuplicateDemFileNameError()

    try:
        size = _write_upload_file(upload, dest_path)
    except FileExistsError as exc:
        raise DuplicateDemFileNameError() from exc
    except Exception as exc:
        _remove_file_safely(dest_path)
        raise DemFileSaveError() from exc

    try:
        dem_row = create_dem(
            dem_id=uuid4(),
            file_name=filename,
            file_path=file_rel_path,
            file_url=f"/assets/{file_rel_path}",
        )
    except DuplicateDemPathError as exc:
        _remove_file_safely(dest_path)
        raise DuplicateDemFileNameError() from exc
    except Exception as exc:
        _remove_file_safely(dest_path)
        raise DemFileSaveError() from exc

    return {
        "dem_id": dem_row["dem_id"],
        "file_name": dem_row["file_name"],
        "file_path": dem_row["file_path"],
        "file_url": dem_row["file_url"],
        "file_size": size,
        "created_at": dem_row["created_at"],
    }


def list_dem_files(limit: int = 100, offset: int = 0) -> list[dict]:
    return list_dems(limit=limit, offset=offset)
