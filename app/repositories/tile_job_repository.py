from uuid import UUID

from psycopg2 import errors

from app.db.connection import get_db_connection


class ProjectNotFoundError(Exception):
    pass


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

            tile_job_ids = [str(row[0]) for row in rows]
            tilesets_map = {}
            if tile_job_ids:
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
                        WHERE tile_job_id = ANY(%s::uuid[])
                        ORDER BY ifc_class
                        """,
                        (tile_job_ids,),
                    )
                    for row in cur.fetchall():
                        tile_job_id = row[0]
                        tilesets_map.setdefault(tile_job_id, []).append(
                            {
                                "ifc_class": row[1],
                                "tileset_url": row[2],
                                "status": row[3],
                                "error": row[4],
                                "updated_at": row[5],
                            }
                        )

            return [
                {
                    "tile_job_id": row[0],
                    "project_id": row[1],
                    "tile_name": row[2],
                    "status": row[3],
                    "total_classes": row[4],
                    "done_classes": row[5],
                    "failed_classes": row[6],
                    "tile_path": row[7],
                    "tilesets": tilesets_map.get(row[0], []),
                    "started_at": row[8],
                    "finished_at": row[9],
                    "created_at": row[10],
                }
                for row in rows
            ]
    finally:
        conn.close()


def create_tile_job(
    project_id: UUID,
    tile_job_id: UUID,
    tile_name: str | None = None,
) -> dict:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tile_job (tile_job_id, project_id, tile_name, status)
                    VALUES (%s, %s, %s, 'PENDING')
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
                    (str(tile_job_id), str(project_id), tile_name),
                )
                row = cur.fetchone()
                return {
                    "tile_job_id": row[0],
                    "project_id": row[1],
                    "tile_name": row[2],
                    "status": row[3],
                    "total_classes": row[4],
                    "done_classes": row[5],
                    "failed_classes": row[6],
                    "tile_path": row[7],
                    "tilesets": [],
                    "started_at": row[8],
                    "finished_at": row[9],
                    "created_at": row[10],
                }
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

            tilesets = []
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        ifc_class,
                        tileset_url,
                        status,
                        error,
                        updated_at
                    FROM tileset
                    WHERE tile_job_id = %s
                    ORDER BY ifc_class
                    """,
                    (str(tile_job_id),),
                )
                for tileset_row in cur.fetchall():
                    tilesets.append(
                        {
                            "ifc_class": tileset_row[0],
                            "tileset_url": tileset_row[1],
                            "status": tileset_row[2],
                            "error": tileset_row[3],
                            "updated_at": tileset_row[4],
                        }
                    )

            return {
                "tile_job_id": row[0],
                "project_id": row[1],
                "tile_name": row[2],
                "status": row[3],
                "total_classes": row[4],
                "done_classes": row[5],
                "failed_classes": row[6],
                "tile_path": row[7],
                "tilesets": tilesets,
                "started_at": row[8],
                "finished_at": row[9],
                "created_at": row[10],
            }
    finally:
        conn.close()
