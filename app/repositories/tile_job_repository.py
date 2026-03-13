from uuid import UUID

from psycopg2 import errors

from app.db.connection import get_db_connection


class ProjectNotFoundError(Exception):
    pass


def _map_tile_job_row(row) -> dict:
    return {
        "tile_job_id": row[0],
        "project_id": row[1],
        "tile_name": row[2],
        "status": row[3],
        "total_classes": row[4],
        "done_classes": row[5],
        "failed_classes": row[6],
        "tile_path": row[7],
        "started_at": row[8],
        "finished_at": row[9],
        "created_at": row[10],
    }


def list_tile_jobs_by_project(
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
                        tile_job_id,
                        project_id,
                        tile_name,
                        status,
                        total_classes,
                        done_classes,
                        failed_classes,
                        tile_path,
                        started_at,
                        finished_at,
                        created_at
                    FROM tile_job
                    WHERE project_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (str(project_id), limit, offset),
                )
                rows = cur.fetchall()

            return [_map_tile_job_row(row) for row in rows]
    finally:
        conn.close()


def create_tile_job(
    project_id: UUID,
    tile_job_id: UUID,
    tile_name: str | None = None,
    tile_path: str | None = None,
) -> dict:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tile_job (tile_job_id, project_id, tile_name, status, tile_path)
                    VALUES (%s, %s, %s, 'PENDING', %s)
                    RETURNING
                        tile_job_id,
                        project_id,
                        tile_name,
                        status,
                        total_classes,
                        done_classes,
                        failed_classes,
                        tile_path,
                        started_at,
                        finished_at,
                        created_at
                    """,
                    (str(tile_job_id), str(project_id), tile_name, tile_path),
                )
                row = cur.fetchone()
                return _map_tile_job_row(row)
    except errors.ForeignKeyViolation as exc:
        raise ProjectNotFoundError() from exc
    finally:
        conn.close()


def get_tile_job_by_project(
    project_id: UUID,
    tile_job_id: UUID,
) -> dict | None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        tile_job_id,
                        project_id,
                        tile_name,
                        status,
                        total_classes,
                        done_classes,
                        failed_classes,
                        tile_path,
                        started_at,
                        finished_at,
                        created_at
                    FROM tile_job
                    WHERE project_id = %s AND tile_job_id = %s
                    """,
                    (str(project_id), str(tile_job_id)),
                )
                row = cur.fetchone()
                if not row:
                    return None

            return _map_tile_job_row(row)
    finally:
        conn.close()


def list_tilesets_by_tile_job_ids(tile_job_ids: list[UUID | str]) -> dict[str, list[dict]]:
    if not tile_job_ids:
        return {}

    keys = list({str(tile_job_id) for tile_job_id in tile_job_ids})

    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        tile_job_id,
                        ifc_class,
                        tileset_url,
                        status,
                        error,
                        updated_at
                    FROM tileset
                    WHERE tile_job_id = ANY(%s)
                    ORDER BY tile_job_id, ifc_class
                    """,
                    (keys,),
                )
                rows = cur.fetchall()

            grouped: dict[str, list[dict]] = {key: [] for key in keys}
            for row in rows:
                grouped[str(row[0])].append(
                    {
                        "ifc_class": row[1],
                        "tileset_url": row[2],
                        "status": row[3],
                        "error": row[4],
                        "updated_at": row[5],
                    }
                )
            return grouped
    finally:
        conn.close()


def list_tilesets_by_tile_job(tile_job_id: UUID | str) -> list[dict]:
    return list_tilesets_by_tile_job_ids([tile_job_id]).get(str(tile_job_id), [])
