from enum import StrEnum


class JobStatus(StrEnum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"


RUNNING_JOB_STATUSES = frozenset({JobStatus.EXTRACTING, JobStatus.ANALYZING, JobStatus.SUMMARIZING})
PROGRESS_JOB_STATUSES = frozenset({JobStatus.ANALYZING, JobStatus.SUMMARIZING})
