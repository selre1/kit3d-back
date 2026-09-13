import json
from uuid import UUID

from psycopg2 import errors

from app.db.connection import get_db_connection


class ProjectNotFoundError(Exception):
    pass


SELECT_COLUMNS = """
    fbx_job_id,
    project_id,
    tile_name,
    task_id,
    status,
    options,
    input_dir,
    tileset_url,
    output_dir,
    error,
    created_at,
    started_at,
    finished_at
"""


def _map_row(row) -> dict:
    return {
        "fbx_job_id": row[0],
        "project_id": row[1],
        "tile_name": row[2],
        "task_id": row[3],
        "status": row[4],
        "options": row[5],
        "input_dir": row[6],
        "tileset_url": row[7],
        "output_dir": row[8],
        "error": row[9],
        "created_at": row[10],
        "started_at": row[11],
        "finished_at": row[12],
    }


def create_fbx_tile_job(
    fbx_job_id: UUID,
    project_id: UUID,
    task_id: str,
    tile_name: str | None,
    input_dir: str,
    options: dict,
) -> dict:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO fbx_tile_job
                        (fbx_job_id, project_id, tile_name, task_id, status, options, input_dir, started_at)
                    VALUES (%s, %s, %s, %s, 'PENDING', %s::jsonb, %s, NOW())
                    RETURNING {SELECT_COLUMNS}
                    """,
                    (
                        str(fbx_job_id),
                        str(project_id),
                        tile_name,
                        task_id,
                        json.dumps(options),
                        input_dir,
                    ),
                )
                return _map_row(cur.fetchone())
    except errors.ForeignKeyViolation as exc:
        raise ProjectNotFoundError() from exc
    finally:
        conn.close()


def list_fbx_tile_jobs_by_project(
    project_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {SELECT_COLUMNS}
                    FROM fbx_tile_job
                    WHERE project_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (str(project_id), limit, offset),
                )
                return [_map_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_fbx_tile_job(project_id: UUID, fbx_job_id: UUID) -> dict | None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {SELECT_COLUMNS}
                    FROM fbx_tile_job
                    WHERE project_id = %s AND fbx_job_id = %s
                    """,
                    (str(project_id), str(fbx_job_id)),
                )
                row = cur.fetchone()
                return _map_row(row) if row else None
    finally:
        conn.close()


def save_fbx_tile_job_result(
    fbx_job_id: UUID,
    status: str,
    tileset_url: str | None,
    output_dir: str | None,
    error: str | None,
) -> None:
    """워커가 끝낸 결과를 DB 에 보존한다. Redis 결과는 24시간 뒤 사라진다."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE fbx_tile_job
                    SET status = %s,
                        tileset_url = %s,
                        output_dir = %s,
                        error = %s,
                        finished_at = NOW()
                    WHERE fbx_job_id = %s
                    """,
                    (status, tileset_url, output_dir, error, str(fbx_job_id)),
                )
    finally:
        conn.close()
