from datetime import datetime
import os
from pathlib import Path

from fastapi import UploadFile


class InvalidDemFileTypeError(Exception):
    pass


class DuplicateDemFileNameError(Exception):
    pass


class DemFileSaveError(Exception):
    pass


def save_dem_file(upload: UploadFile) -> dict:
    filename = Path(upload.filename or "").name
    ext = Path(filename).suffix.lower()
    if not filename or ext not in {".tif", ".tiff"}:
        raise InvalidDemFileTypeError()

    upload_root = Path(os.getenv("UPLOAD_DIR", "/data/assets"))
    dem_tif_dir = upload_root / "dem" / "tif"
    dem_tif_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dem_tif_dir / filename
    if dest_path.exists():
        raise DuplicateDemFileNameError()

    size = 0
    try:
        with open(dest_path, "xb") as out_file:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                out_file.write(chunk)
                size += len(chunk)
    except DuplicateDemFileNameError:
        raise
    except Exception as exc:
        raise DemFileSaveError() from exc

    relative_url = f"/assets/dem/tif/{filename}"
    return {
        "file_name": filename,
        "file_path": str(dest_path),
        "file_url": relative_url,
        "file_size": size,
        "uploaded_at": datetime.now(),
    }
