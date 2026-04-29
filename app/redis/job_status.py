from enum import Enum


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


def normalize_job_status(value, default: JobStatus = JobStatus.PENDING) -> JobStatus:
    text = str(value or "").upper()
    for status in JobStatus:
        if status.value == text:
            return status
    return default