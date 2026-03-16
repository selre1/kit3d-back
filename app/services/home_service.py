from app.repositories.import_job_repository import list_recent_upload_jobs_for_projects
from app.repositories.project_repository import fetch_projects
from app.services.import_job_service import get_import_status


def get_home_summary(
    project_limit: int = 20,
    project_offset: int = 0,
    project_span: int = 8,
    import_limit: int = 10,
) -> dict:
    projects = fetch_projects(limit=project_limit, offset=project_offset)
    target_projects = projects[: max(project_span, 0)]
    target_project_ids = [project["project_id"] for project in target_projects]

    uploads = list_recent_upload_jobs_for_projects(
        project_ids=target_project_ids,
        per_project_limit=max(import_limit, 0),
    )

    return {
        "projects": projects,
        "uploads": [get_import_status(item) for item in uploads],
    }
