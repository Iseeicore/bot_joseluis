from src.document_analysis.domain.ports import JobTransaction
from src.shared.enums.job_status import RUNNING_JOB_STATUSES
from src.shared.types.clock import Clock
from src.shared.utils.format_timestamp import format_timestamp


def recover_interrupted_jobs(open_jobs: JobTransaction, now: Clock) -> int:
    with open_jobs() as jobs:
        return jobs.requeue_jobs(RUNNING_JOB_STATUSES, format_timestamp(now()))
