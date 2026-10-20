from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request

from src.document_analysis.application.submit_job import JobSubmission, SubmittedJob
from src.document_analysis.domain.models import Job


@dataclass(frozen=True)
class JobUseCases:
    submit: Callable[[JobSubmission], SubmittedJob]
    get: Callable[[str], Job]


def read_job_use_cases(request: Request) -> JobUseCases:
    return request.app.state.job_use_cases
