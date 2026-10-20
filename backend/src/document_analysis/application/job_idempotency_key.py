import hashlib
import json
from dataclasses import astuple, dataclass

from src.document_analysis.domain.models import GenerationOptions
from src.shared.constants.texts.jobs import DEFAULT_JOB_REQUEST_TEXT


@dataclass(frozen=True)
class JobIdentity:
    notes_prompt: str
    summary_prompt: str
    notes_options: GenerationOptions
    summary_options: GenerationOptions
    summary_batch_chars: int


def normalize_request(request: str | None) -> str:
    stripped = (request or "").strip()
    return stripped or DEFAULT_JOB_REQUEST_TEXT


def job_idempotency_key(file_sha256: str, request: str, ocr: bool, identity: JobIdentity) -> str:
    parts = [
        file_sha256,
        request,
        ocr,
        identity.notes_prompt,
        identity.summary_prompt,
        list(astuple(identity.notes_options)),
        list(astuple(identity.summary_options)),
        identity.summary_batch_chars,
    ]
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()
