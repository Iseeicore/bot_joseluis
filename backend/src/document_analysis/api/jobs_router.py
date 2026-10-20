from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from src.document_analysis.api.job_dependencies import JobUseCases, read_job_use_cases
from src.document_analysis.api.job_schemas import JobProgressResponse, JobResponse, SubmitJobResponse
from src.document_analysis.application.submit_job import JobSubmission
from src.document_analysis.domain.models import Job
from src.shared.constants.routes import JOB_PATH, JOBS_PATH, job_status_path
from src.shared.constants.texts.jobs import UNNAMED_UPLOAD_TEXT

router = APIRouter()
UseCases = Annotated[JobUseCases, Depends(read_job_use_cases)]


def to_job_response(job: Job) -> JobResponse:
    progress = job.visible_progress
    return JobResponse(
        job_id=job.id,
        document_name=job.document_name,
        status=job.status,
        progress=None if progress is None else JobProgressResponse(done=progress.done, total=progress.total),
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post(JOBS_PATH, status_code=HTTPStatus.ACCEPTED)
def submit_job_endpoint(
    file: Annotated[UploadFile, File()],
    response: Response,
    use_cases: UseCases,
    request: Annotated[str | None, Form()] = None,
    ocr: Annotated[bool, Form()] = False,
) -> SubmitJobResponse:
    submission = JobSubmission(content=file.file, file_name=file.filename or UNNAMED_UPLOAD_TEXT, request=request, ocr=ocr)
    submitted = use_cases.submit(submission)
    response.status_code = HTTPStatus.ACCEPTED if submitted.created else HTTPStatus.OK
    return SubmitJobResponse(job_id=submitted.job_id, status=submitted.status, status_url=job_status_path(submitted.job_id))


@router.get(JOB_PATH)
def read_job_endpoint(job_id: UUID, use_cases: UseCases) -> JobResponse:
    return to_job_response(use_cases.get(str(job_id)))
