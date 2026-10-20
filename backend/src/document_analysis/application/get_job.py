from src.document_analysis.domain.models import Job
from src.document_analysis.domain.ports import JobTransaction
from src.shared.errors.job_not_found_error import JobNotFoundError


def get_job(job_id: str, open_jobs: JobTransaction) -> Job:
    with open_jobs() as jobs:
        job = jobs.get_job(job_id)
    if job is None:
        raise JobNotFoundError(job_id)
    return job
