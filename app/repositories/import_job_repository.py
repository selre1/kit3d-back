from uuid import UUID

from psycopg2 import errors

from app.db.connection import get_db_connection


class ProjectNotFoundError(Exception):
    pass


def list_upload_jobs_by_project(
    project_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        f.file_id,
                        f.project_id,
                        f.file_name,
                        f.file_format,
                        f.file_path,
                        f.file_url,
                        f.file_size,
                        f.uploaded_at,
                        j.job_id,
                        j.job_type,
                        j.status,
                        j.started_at,
                        j.finished_at,
                        j.created_at
                    FROM upload_file f
                    LEFT JOIN import_job j ON j.file_id = f.file_id
                    WHERE f.project_id = %s
                    ORDER BY f.uploaded_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (str(project_id), limit, offset),
                )
                rows = cur.fetchall()

            return [
                {
                    "file_id": row[0],
                    "project_id": row[1],
                    "file_name": row[2],
                    "file_format": row[3],
                    "file_path": row[4],
                    "file_url": row[5],
                    "file_size": row[6],
                    "uploaded_at": row[7],
                    "job_id": row[8],
                    "job_type": row[9],
                    "status": row[10],
                    "started_at": row[11],
                    "finished_at": row[12],
                    "created_at": row[13],
                }
                for row in rows
            ]
    finally:
        conn.close()


def get_upload_job_by_id(job_id: UUID) -> dict | None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        f.file_id,
                        f.project_id,
                        f.file_name,
                        f.file_format,
                        f.file_path,
                        f.file_url,
                        f.file_size,
                        f.uploaded_at,
                        j.job_id,
                        j.job_type,
                        j.status,
                        j.started_at,
                        j.finished_at,
                        j.created_at
                    FROM import_job j
                    JOIN upload_file f ON f.file_id = j.file_id
                    WHERE j.job_id = %s
                    """,
                    (str(job_id),),
                )
                row = cur.fetchone()
                if not row:
                    return None

                return {
                    "file_id": row[0],
                    "project_id": row[1],
                    "file_name": row[2],
                    "file_format": row[3],
                    "file_path": row[4],
                    "file_url": row[5],
                    "file_size": row[6],
                    "uploaded_at": row[7],
                    "job_id": row[8],
                    "job_type": row[9],
                    "status": row[10],
                    "started_at": row[11],
                    "finished_at": row[12],
                    "created_at": row[13],
                }
    finally:
        conn.close()


def get_upload_file_by_project(
    project_id: UUID,
    file_id: int,
) -> dict | None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        file_id,
                        project_id,
                        file_name,
                        file_format,
                        file_path,
                        file_url,
                        file_size,
                        uploaded_at
                    FROM upload_file
                    WHERE project_id = %s AND file_id = %s
                    """,
                    (str(project_id), file_id),
                )
                row = cur.fetchone()
                if not row:
                    return None

                return {
                    "file_id": row[0],
                    "project_id": row[1],
                    "file_name": row[2],
                    "file_format": row[3],
                    "file_path": row[4],
                    "file_url": row[5],
                    "file_size": row[6],
                    "uploaded_at": row[7],
                }
    finally:
        conn.close()


def create_upload_job(
    project_id: UUID,
    job_id: UUID,
    file_name: str,
    file_format: str,
    file_path: str,
    file_url: str,
    file_size: int | None,
) -> dict:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO upload_file (project_id, file_name, file_format, file_path, file_url, file_size)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING file_id, uploaded_at
                    """,
                    (str(project_id), file_name, file_format, file_path, file_url, file_size),
                )
                file_row = cur.fetchone()
                file_id = file_row[0]
                uploaded_at = file_row[1]

                cur.execute(
                    """
                    INSERT INTO import_job (job_id, project_id, file_id)
                    VALUES (%s, %s, %s)
                    RETURNING job_id, job_type, status, started_at, finished_at, created_at
                    """,
                    (str(job_id), str(project_id), file_id),
                )
                job_row = cur.fetchone()

                return {
                    "file_id": file_id,
                    "uploaded_at": uploaded_at,
                    "job_id": job_row[0],
                    "job_type": job_row[1],
                    "status": job_row[2],
                    "started_at": job_row[3],
                    "finished_at": job_row[4],
                    "created_at": job_row[5],
                }
    except errors.ForeignKeyViolation as exc:
        raise ProjectNotFoundError() from exc
    finally:
        conn.close()

def reset_job_for_retry(job_id: UUID) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE import_job
                    SET status = 'PENDING', started_at = NULL, finished_at = NULL
                    WHERE job_id = %s
                    """,
                    (str(job_id),),
                )
                return cur.rowcount > 0
    finally:
        conn.close()