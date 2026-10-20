"""
title: Analizador de documentos
description: Envía el PDF adjunto al servicio de análisis de documentos y responde con su resumen.
version: 0.2.0
required_open_webui_version: 0.11.4
"""

import asyncio
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

PIPE_ID = "document-analysis"
PIPE_NAME = "Analizador de documentos"

JOBS_PATH = "/jobs"
PDF_CONTENT_TYPE = "application/pdf"
PDF_EXTENSION = ".pdf"
FILE_ATTACHMENT_TYPE = "file"
USER_ROLE = "user"
ADMIN_ROLE = "admin"
TEXT_CONTENT_PART = "text"
STATUS_EVENT_TYPE = "status"
FORM_BOOLEANS = {True: "true", False: "false"}
ATTACHED_FILES_BLOCK = re.compile(r"^\s*<attached_files>.*?</attached_files>\s*", re.DOTALL)

MAX_SUBMIT_ATTEMPTS = 3
MAX_UNVERIFIED_NOTES_LISTED = 5
PROGRESS_REPORT_STEPS = 10

DEFAULT_BACKEND_URL = "http://backend:8000"
DEFAULT_POLL_INTERVAL_SECONDS = 3.0
DEFAULT_MAX_WAIT_SECONDS = 3600.0
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0

MISSING_PDF_REPLY = "Adjunta un documento PDF y escribe en el mismo mensaje qué quieres saber de él."
NOT_PDF_REPLY = "El archivo «{name}» no es un PDF. Adjunta el documento en formato PDF."
FILE_UNAVAILABLE_REPLY = "No pude leer el archivo adjunto. Vuelve a adjuntarlo e inténtalo de nuevo."
SERVICE_UNAVAILABLE_REPLY = "No pude conectar con el servicio de análisis. Inténtalo de nuevo en unos minutos."
UNEXPECTED_RESPONSE_REPLY = "El servicio de análisis respondió de forma inesperada. Inténtalo de nuevo más tarde."
JOB_NOT_FOUND_REPLY = "El servicio de análisis ya no encuentra este trabajo. Vuelve a enviar el archivo con tu pregunta."
JOB_FAILED_REPLY = "El análisis del documento falló."
STILL_PROCESSING_REPLY = (
    "El documento sigue en proceso. Vuelve a enviar el mismo archivo con la misma pregunta más tarde: "
    "se retomará el mismo trabajo, sin empezar de nuevo."
)

TRUNCATED_SUMMARY_NOTE = (
    "_La respuesta se cortó por su longitud y puede estar incompleta. Haz una pregunta más específica para obtener el detalle._"
)
FAILED_FRAGMENTS_NOTE = "_Fragmentos que no se pudieron analizar: {count}. El resumen puede estar incompleto._"
UNVERIFIED_FACTS_HEADER = "**Datos por verificar:** estas cifras o siglas de las notas no aparecen literalmente en el documento."
UNVERIFIED_FACTS_ITEM = "- {pages}: {facts}"
UNVERIFIED_FACTS_REMAINDER = "- Otros fragmentos con datos por verificar: {count}."
SINGLE_PAGE_LABEL = "Pág. {page}"
PAGE_RANGE_LABEL = "Págs. {first}-{last}"
FACTS_SEPARATOR = ", "
LINE_SEPARATOR = "\n"
SECTION_SEPARATOR = "\n\n"

SENDING_STATUS = "Enviando el documento…"
RECONNECTING_STATUS = "Reconectando con el servicio de análisis…"
QUEUED_STATUS = "En cola…"
EXTRACTING_STATUS = "Extrayendo texto del PDF…"
ANALYZING_STATUS = "Analizando el documento…"
ANALYZING_PROGRESS_STATUS = "Analizando fragmento {done}/{total}…"
SUMMARIZING_STATUS = "Redactando el resumen…"
SUMMARIZING_PROGRESS_STATUS = "Redactando el resumen: parte {done}/{total}…"
COMPLETED_STATUS = "Análisis completado"
FAILED_STATUS = "El análisis falló"
STILL_PROCESSING_STATUS = "El análisis sigue en curso"
INTERRUPTED_STATUS = "Análisis interrumpido"


class JobStatus(StrEnum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"


EventEmitter = Callable[[dict[str, Any]], Awaitable[None]]


class UserFacingError(Exception):
    def __init__(self, reply: str) -> None:
        super().__init__(reply)
        self.reply = reply


@dataclass(frozen=True)
class Attachment:
    file_id: str
    name: str
    content_type: str

    @property
    def is_pdf(self) -> bool:
        return self.content_type == PDF_CONTENT_TYPE or self.name.lower().endswith(PDF_EXTENSION)


@dataclass(frozen=True)
class StoredFile:
    owner_id: str
    content: bytes


@dataclass(frozen=True)
class JobSubmission:
    file_name: str
    content: bytes
    request: str
    ocr: bool


@dataclass(frozen=True)
class TerminalOutcome:
    compose_reply: Callable[[dict[str, Any]], str]
    status_description: str


class StatusReporter:
    def __init__(self, emitter: EventEmitter | None) -> None:
        self._emitter = emitter
        self._last_event: tuple[str, bool] | None = None

    async def report(self, description: str, done: bool = False) -> None:
        event = (description, done)
        if self._emitter is None or event == self._last_event:
            return
        self._last_event = event
        await self._emitter({"type": STATUS_EVENT_TYPE, "data": {"description": description, "done": done}})

    async def interrupt(self) -> None:
        if self._last_event is None:
            return
        await self.report(INTERRUPTED_STATUS, done=True)


def progress_step(progress: dict[str, Any]) -> int:
    return progress["done"] * PROGRESS_REPORT_STEPS // progress["total"]


class ProgressThrottle:
    def __init__(self) -> None:
        self._stage: tuple[JobStatus, int | None] | None = None
        self._step = 0

    def allows(self, status: JobStatus, progress: dict[str, Any] | None) -> bool:
        if progress is None:
            self._stage = (status, None)
            return True
        stage, step = (status, progress["total"]), progress_step(progress)
        is_due = stage != self._stage or step != self._step or progress["done"] >= progress["total"]
        if is_due:
            self._stage, self._step = stage, step
        return is_due


async def load_open_webui_file(file_id: str) -> StoredFile | None:
    from open_webui.models.files import Files
    from open_webui.storage.provider import Storage

    record = await Files.get_file_by_id(file_id)
    if record is None or not record.path:
        return None
    try:
        local_path = await asyncio.to_thread(Storage.get_file, record.path)
        content = await asyncio.to_thread(Path(local_path).read_bytes)
    except OSError:
        return None
    return StoredFile(owner_id=record.user_id, content=content)


def parse_attachment(item: dict[str, Any]) -> Attachment | None:
    if item.get("type") != FILE_ATTACHMENT_TYPE:
        return None
    return Attachment(file_id=item.get("id") or "", name=item.get("name") or "", content_type=item.get("content_type") or "")


def select_latest_attachment(files: list[dict[str, Any]]) -> Attachment:
    attachments = [attachment for attachment in map(parse_attachment, files) if attachment is not None]
    if not attachments:
        raise UserFacingError(MISSING_PDF_REPLY)
    latest = attachments[-1]
    if not latest.is_pdf:
        raise UserFacingError(NOT_PDF_REPLY.format(name=latest.name))
    return latest


def can_read(stored: StoredFile, user: dict[str, Any]) -> bool:
    return stored.owner_id == user.get("id") or user.get("role") == ADMIN_ROLE


def message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return LINE_SEPARATOR.join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == TEXT_CONTENT_PART)


def last_user_message_text(messages: list[dict[str, Any]]) -> str:
    user_messages = [message for message in messages if message.get("role") == USER_ROLE]
    if not user_messages:
        return ""
    return message_text(user_messages[-1].get("content"))


def extract_user_request(body: dict[str, Any], metadata: dict[str, Any]) -> str:
    prompt = metadata.get("user_prompt") or last_user_message_text(body.get("messages") or [])
    return ATTACHED_FILES_BLOCK.sub("", prompt, count=1).strip()


async def send_safely(request: Awaitable[httpx.Response]) -> httpx.Response | None:
    try:
        return await request
    except httpx.TransportError:
        return None


def is_transient(response: httpx.Response | None) -> bool:
    return response is None or response.is_server_error


def read_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        raise UserFacingError(UNEXPECTED_RESPONSE_REPLY) from None
    if not isinstance(payload, dict):
        raise UserFacingError(UNEXPECTED_RESPONSE_REPLY)
    return payload


def read_error_message(response: httpx.Response) -> str:
    return read_json(response).get("message") or UNEXPECTED_RESPONSE_REPLY


def read_status_url(response: httpx.Response) -> str:
    if not response.is_success:
        raise UserFacingError(read_error_message(response))
    status_url = read_json(response).get("statusUrl")
    if not isinstance(status_url, str):
        raise UserFacingError(UNEXPECTED_RESPONSE_REPLY)
    return status_url


def read_job_status(job: dict[str, Any]) -> JobStatus:
    try:
        return JobStatus(job.get("status"))
    except ValueError:
        raise UserFacingError(UNEXPECTED_RESPONSE_REPLY) from None


async def submit_job(client: httpx.AsyncClient, submission: JobSubmission, reporter: StatusReporter, retry_delay: float) -> str:
    files = {"file": (submission.file_name, submission.content, PDF_CONTENT_TYPE)}
    data = {"request": submission.request, "ocr": FORM_BOOLEANS[submission.ocr]}
    for _ in range(MAX_SUBMIT_ATTEMPTS):
        response = await send_safely(client.post(JOBS_PATH, files=files, data=data))
        if not is_transient(response):
            return read_status_url(response)
        await reporter.report(RECONNECTING_STATUS)
        await asyncio.sleep(retry_delay)
    raise UserFacingError(SERVICE_UNAVAILABLE_REPLY)


async def fetch_job(client: httpx.AsyncClient, status_url: str, reporter: StatusReporter) -> dict[str, Any] | None:
    response = await send_safely(client.get(status_url))
    if is_transient(response):
        await reporter.report(RECONNECTING_STATUS)
        return None
    if response.status_code == httpx.codes.NOT_FOUND:
        raise UserFacingError(JOB_NOT_FOUND_REPLY)
    if not response.is_success:
        raise UserFacingError(read_error_message(response))
    return read_json(response)


def progress_describer(idle_status: str, progress_status: str) -> Callable[[dict[str, Any]], str]:
    def describe(job: dict[str, Any]) -> str:
        progress = job.get("progress")
        if progress is None:
            return idle_status
        return progress_status.format(done=progress["done"], total=progress["total"])

    return describe


RUNNING_STATUS_DESCRIBERS: dict[JobStatus, Callable[[dict[str, Any]], str]] = {
    JobStatus.QUEUED: lambda _job: QUEUED_STATUS,
    JobStatus.EXTRACTING: lambda _job: EXTRACTING_STATUS,
    JobStatus.ANALYZING: progress_describer(ANALYZING_STATUS, ANALYZING_PROGRESS_STATUS),
    JobStatus.SUMMARIZING: progress_describer(SUMMARIZING_STATUS, SUMMARIZING_PROGRESS_STATUS),
}


async def wait_for_job(
    client: httpx.AsyncClient, status_url: str, valves: "Pipe.Valves", reporter: StatusReporter
) -> dict[str, Any] | None:
    deadline = time.monotonic() + valves.max_wait_seconds
    throttle = ProgressThrottle()
    while True:
        job = await fetch_job(client, status_url, reporter)
        status = read_job_status(job) if job is not None else None
        if status in TERMINAL_OUTCOMES:
            return job
        if status is not None and throttle.allows(status, job.get("progress")):
            await reporter.report(RUNNING_STATUS_DESCRIBERS[status](job))
        if time.monotonic() >= deadline:
            return None
        await asyncio.sleep(valves.poll_interval_seconds)


def format_pages(first_page: int, last_page: int) -> str:
    if first_page == last_page:
        return SINGLE_PAGE_LABEL.format(page=first_page)
    return PAGE_RANGE_LABEL.format(first=first_page, last=last_page)


def format_unverified_note(note: dict[str, Any]) -> str:
    pages = format_pages(note["firstPage"], note["lastPage"])
    return UNVERIFIED_FACTS_ITEM.format(pages=pages, facts=FACTS_SEPARATOR.join(note["unverifiedFacts"]))


def unverified_facts_sections(notes: list[dict[str, Any]]) -> list[str]:
    flagged = [note for note in notes if note["unverifiedFacts"]]
    if not flagged:
        return []
    lines = [UNVERIFIED_FACTS_HEADER, *map(format_unverified_note, flagged[:MAX_UNVERIFIED_NOTES_LISTED])]
    remainder = len(flagged) - MAX_UNVERIFIED_NOTES_LISTED
    if remainder > 0:
        lines.append(UNVERIFIED_FACTS_REMAINDER.format(count=remainder))
    return [LINE_SEPARATOR.join(lines)]


def failed_fragments_sections(failed_indexes: list[int]) -> list[str]:
    if not failed_indexes:
        return []
    return [FAILED_FRAGMENTS_NOTE.format(count=len(failed_indexes))]


def truncated_summary_sections(summary_truncated: bool) -> list[str]:
    if not summary_truncated:
        return []
    return [TRUNCATED_SUMMARY_NOTE]


def compose_completed_reply(job: dict[str, Any]) -> str:
    result = job["result"]
    sections = [
        result["summary"],
        *truncated_summary_sections(result.get("summaryTruncated", False)),
        *failed_fragments_sections(result["failedIndexes"]),
        *unverified_facts_sections(result["notes"]),
    ]
    return SECTION_SEPARATOR.join(sections)


def compose_failed_reply(job: dict[str, Any]) -> str:
    error = job.get("error") or {}
    return error.get("message") or JOB_FAILED_REPLY


TERMINAL_OUTCOMES: dict[JobStatus, TerminalOutcome] = {
    JobStatus.COMPLETED: TerminalOutcome(compose_completed_reply, COMPLETED_STATUS),
    JobStatus.FAILED: TerminalOutcome(compose_failed_reply, FAILED_STATUS),
}


class Pipe:
    class Valves(BaseModel):
        backend_url: str = Field(default=DEFAULT_BACKEND_URL, description="URL base del servicio de análisis de documentos.")
        poll_interval_seconds: float = Field(default=DEFAULT_POLL_INTERVAL_SECONDS, ge=0, description="Segundos entre consultas de estado.")
        max_wait_seconds: float = Field(default=DEFAULT_MAX_WAIT_SECONDS, ge=0, description="Espera máxima por un análisis, en segundos.")
        request_timeout_seconds: float = Field(
            default=DEFAULT_REQUEST_TIMEOUT_SECONDS, gt=0, description="Tiempo máximo de cada petición HTTP, en segundos."
        )
        ocr: bool = Field(default=False, description="Aplicar OCR a las páginas escaneadas.")

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.transport: httpx.AsyncBaseTransport | None = None
        self.load_stored_file: Callable[[str], Awaitable[StoredFile | None]] = load_open_webui_file

    def pipes(self) -> list[dict[str, str]]:
        return [{"id": PIPE_ID, "name": PIPE_NAME}]

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any] | None = None,
        __metadata__: dict[str, Any] | None = None,
        __files__: list[dict[str, Any]] | None = None,
        __event_emitter__: EventEmitter | None = None,
        __task__: str | None = None,
    ) -> str:
        if __task__:
            return ""
        reporter = StatusReporter(__event_emitter__)
        try:
            return await self._analyze(body, __user__ or {}, __metadata__ or {}, __files__ or [], reporter)
        except UserFacingError as error:
            await reporter.interrupt()
            return error.reply

    async def _analyze(
        self, body: dict[str, Any], user: dict[str, Any], metadata: dict[str, Any], files: list[dict[str, Any]], reporter: StatusReporter
    ) -> str:
        attachment = select_latest_attachment(files)
        content = await self._read_pdf(attachment, user)
        submission = JobSubmission(attachment.name, content, extract_user_request(body, metadata), self.valves.ocr)
        async with self._create_client() as client:
            await reporter.report(SENDING_STATUS)
            status_url = await submit_job(client, submission, reporter, self.valves.poll_interval_seconds)
            job = await wait_for_job(client, status_url, self.valves, reporter)
        if job is None:
            await reporter.report(STILL_PROCESSING_STATUS, done=True)
            return STILL_PROCESSING_REPLY
        outcome = TERMINAL_OUTCOMES[read_job_status(job)]
        await reporter.report(outcome.status_description, done=True)
        return outcome.compose_reply(job)

    async def _read_pdf(self, attachment: Attachment, user: dict[str, Any]) -> bytes:
        stored = await self.load_stored_file(attachment.file_id) if attachment.file_id else None
        if stored is None or not can_read(stored, user):
            raise UserFacingError(FILE_UNAVAILABLE_REPLY)
        return stored.content

    def _create_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.valves.backend_url, timeout=self.valves.request_timeout_seconds, transport=self.transport)
