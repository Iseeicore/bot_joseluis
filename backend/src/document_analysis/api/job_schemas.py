from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from src.shared.enums.job_status import JobStatus
from src.shared.types.error_response import ErrorResponse
from src.shared.types.job_result import JobResult


class SubmitJobResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    job_id: str
    status: JobStatus
    status_url: str


class JobProgressResponse(BaseModel):
    done: int
    total: int


class JobResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    job_id: str
    document_name: str
    status: JobStatus
    progress: JobProgressResponse | None
    result: JobResult | None
    error: ErrorResponse | None
    created_at: str
    updated_at: str
