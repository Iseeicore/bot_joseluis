JOBS_PATH = "/jobs"
JOB_PATH = "/jobs/{job_id}"


def job_status_path(job_id: str) -> str:
    return JOB_PATH.format(job_id=job_id)
