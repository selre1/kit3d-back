from uuid import UUID

from psycopg2 import errors

from app.db.connection import get_db_connection


class DuplicateDemPathError(Exception):
    pass


def create_dem(dem_id: UUID, file_name: str, file_path: str, file_url: str) -> dict:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dem (dem_id, file_name, file_path, file_url)
                    VALUES (%s, %s, %s, %s)
                    RETURNING dem_id::text, file_name, file_path, file_url, created_at
                    """,
                    (str(dem_id), file_name, file_path, file_url),
                )
                row = cur.fetchone()
                return {
                    "dem_id": row[0],
                    "file_name": row[1],
                    "file_path": row[2],
                    "file_url": row[3],
                    "created_at": row[4],
                }
    except errors.UniqueViolation as exc:
        raise DuplicateDemPathError() from exc
    finally:
        conn.close()


def list_dems(limit: int = 100, offset: int = 0) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        d.dem_id::text,
                        d.file_name,
                        d.file_path,
                        d.file_url,
                        d.created_at,
                        lj.job_id::text,
                        lj.status,
                        tr.zip_uri,
                        tr.terrain_uri
                    FROM dem d
                    LEFT JOIN LATERAL (
                        SELECT tj.job_id, tj.status, tj.created_at
                        FROM terrain_job tj
                        WHERE tj.dem_id = d.dem_id
                        ORDER BY tj.created_at DESC
                        LIMIT 1
                    ) lj ON true
                    LEFT JOIN terrain_result tr ON tr.job_id = lj.job_id
                    ORDER BY d.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = cur.fetchall()
                return [
                    {
                        "dem_id": row[0],
                        "file_name": row[1],
                        "file_path": row[2],
                        "file_url": row[3],
                        "created_at": row[4],
                        "job_id": row[5],
                        "terrain_status": row[6],
                        "terrain_download_url": row[7],
                        "terrain_tileset_url": row[8],
                    }
                    for row in rows
                ]
    finally:
        conn.close()


def get_dem_by_id(dem_id: UUID | str) -> dict | None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        dem_id::text,
                        file_name,
                        file_path,
                        file_url,
                        created_at
                    FROM dem
                    WHERE dem_id = %s
                    """,
                    (str(dem_id),),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "dem_id": row[0],
                    "file_name": row[1],
                    "file_path": row[2],
                    "file_url": row[3],
                    "created_at": row[4],
                }
    finally:
        conn.close()


def create_terrain_job(job_id: UUID, dem_id: UUID | str, status: str = "PENDING") -> dict:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO terrain_job (job_id, dem_id, status)
                    VALUES (%s, %s, %s)
                    RETURNING job_id::text, dem_id::text, status
                    """,
                    (str(job_id), str(dem_id), status),
                )
                row = cur.fetchone()
                return {
                    "job_id": row[0],
                    "dem_id": row[1],
                    "status": row[2],
                }
    finally:
        conn.close()


def get_terrain_job_by_dem(dem_id: UUID | str) -> dict | None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT job_id::text, dem_id::text, status, task_id, err, created_at, started_at, ended_at
                    FROM terrain_job
                    WHERE dem_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (str(dem_id),),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "job_id": row[0],
                    "dem_id": row[1],
                    "status": row[2],
                    "task_id": row[3],
                    "err": row[4],
                    "created_at": row[5],
                    "started_at": row[6],
                    "ended_at": row[7],
                }
    finally:
        conn.close()


def set_terrain_job_task_id(job_id: UUID | str, task_id: str | None) -> None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE terrain_job
                    SET task_id = %s
                    WHERE job_id = %s
                    """,
                    (task_id, str(job_id)),
                )
    finally:
        conn.close()


def set_terrain_job_failed(job_id: UUID | str, err: str) -> None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE terrain_job
                    SET status = 'FAILED',
                        err = %s,
                        ended_at = NOW()
                    WHERE job_id = %s
                    """,
                    (err[:4000], str(job_id)),
                )
    finally:
        conn.close()
