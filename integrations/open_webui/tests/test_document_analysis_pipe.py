import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from document_analysis_pipe import (
    FILE_UNAVAILABLE_REPLY,
    JOB_NOT_FOUND_REPLY,
    MAX_SUBMIT_ATTEMPTS,
    MISSING_PDF_REPLY,
    RECONNECTING_STATUS,
    RUNNING_STATUS_DESCRIBERS,
    SERVICE_UNAVAILABLE_REPLY,
    STILL_PROCESSING_REPLY,
    TERMINAL_OUTCOMES,
    TRUNCATED_SUMMARY_NOTE,
    JobStatus,
    Pipe,
    StoredFile,
)

BACKEND_URL = "http://backend.test"
JOB_ID = "0b6f4c1e-7d2a-4a8e-9f00-3c1d2e5a6b7c"
STATUS_URL = f"/jobs/{JOB_ID}"
USER = {"id": "user-1", "role": "user"}
PDF_BYTES = b"%PDF-1.4 contenido de prueba"
QUESTION = "¿Qué plazos fija?"
PDF_ITEM = {"type": "file", "id": "file-pdf", "name": "ley.pdf", "content_type": "application/pdf"}
SUMMARY = "La ley fija un plazo de 30 días (pág. 2)."

Step = httpx.Response | Exception


def job_payload(status: str, progress: dict | None = None, result: dict | None = None, error: dict | None = None) -> dict:
    return {
        "jobId": JOB_ID,
        "documentName": "ley.pdf",
        "status": status,
        "progress": progress,
        "result": result,
        "error": error,
        "createdAt": "2026-10-18T10:00:00Z",
        "updatedAt": "2026-10-18T10:00:05Z",
    }


def job_result(failed_indexes: list[int] | None = None, notes: list[dict] | None = None, summary_truncated: bool | None = None) -> dict:
    result = {
        "summary": SUMMARY,
        "notes": notes or [note(0, 1, 2, [])],
        "generatedCount": 1,
        "reusedCount": 0,
        "failedIndexes": failed_indexes or [],
        "scannedPages": [],
    }
    if summary_truncated is not None:
        result["summaryTruncated"] = summary_truncated
    return result


def note(index: int, first_page: int, last_page: int, unverified_facts: list[str]) -> dict:
    return {"index": index, "firstPage": first_page, "lastPage": last_page, "text": "- nota", "unverifiedFacts": unverified_facts}


def job_response(status: str, **fields: Any) -> httpx.Response:
    return httpx.Response(200, json=job_payload(status, **fields))


def completed_response(**result_fields: Any) -> httpx.Response:
    return job_response("completed", result=job_result(**result_fields))


def submitted_response(status_code: int = 202) -> httpx.Response:
    return httpx.Response(status_code, json={"jobId": JOB_ID, "status": "queued", "statusUrl": STATUS_URL})


def api_error(status_code: int, error_code: str, message: str) -> dict:
    return {"statusCode": status_code, "errorCode": error_code, "message": message, "timestamp": "2026-10-18T10:00:00Z", "path": "/jobs"}


class FakeBackend:
    def __init__(self, job_steps: list[Step], submit_steps: list[Step] | None = None) -> None:
        self.job_steps = list(job_steps)
        self.submit_steps = list(submit_steps or [submitted_response()])
        self.submissions: list[httpx.Request] = []
        self.polls: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            self.submissions.append(request)
            return self.next_step(self.submit_steps)
        self.polls.append(request)
        return self.next_step(self.job_steps)

    @staticmethod
    def next_step(steps: list[Step]) -> httpx.Response:
        step = steps.pop(0) if len(steps) > 1 else steps[0]
        if isinstance(step, Exception):
            raise step
        return step


class FakeEmitter:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def __call__(self, event: dict) -> None:
        self.events.append(event)

    @property
    def descriptions(self) -> list[str]:
        return [event["data"]["description"] for event in self.events]


class FakeFileStore:
    def __init__(self, files: dict[str, StoredFile]) -> None:
        self.files = files
        self.requested_ids: list[str] = []

    async def load(self, file_id: str) -> StoredFile | None:
        self.requested_ids.append(file_id)
        return self.files.get(file_id)


def build_pipe(backend: FakeBackend, store: FakeFileStore | None = None, **valves: Any) -> Pipe:
    pipe = Pipe()
    pipe.valves = Pipe.Valves(backend_url=BACKEND_URL, poll_interval_seconds=0, **valves)
    pipe.transport = httpx.MockTransport(backend.handle)
    file_store = store or FakeFileStore({PDF_ITEM["id"]: StoredFile(owner_id=USER["id"], content=PDF_BYTES)})
    pipe.load_stored_file = file_store.load
    return pipe


def run_pipe(
    pipe: Pipe,
    files: list[dict] | None = None,
    emitter: Callable | None = None,
    question: str = QUESTION,
    metadata: dict | None = None,
    task: str | None = None,
) -> str:
    body = {"model": "document_analysis.document-analysis", "stream": True, "messages": [{"role": "user", "content": question}]}
    return asyncio.run(
        pipe.pipe(
            body,
            __user__=USER,
            __metadata__=metadata if metadata is not None else {"user_prompt": question},
            __files__=[PDF_ITEM] if files is None else files,
            __event_emitter__=emitter,
            __task__=task,
        )
    )


def test_pipes_exposes_a_single_document_analysis_model() -> None:
    assert Pipe().pipes() == [{"id": "document-analysis", "name": "Analizador de documentos"}]


def test_every_job_status_has_exactly_one_handler() -> None:
    running = set(RUNNING_STATUS_DESCRIBERS)
    terminal = set(TERMINAL_OUTCOMES)

    assert running | terminal == set(JobStatus)
    assert not running & terminal


def test_completed_job_returns_the_summary_and_reports_each_stage_once() -> None:
    backend = FakeBackend(
        [
            job_response("queued"),
            job_response("queued"),
            job_response("extracting"),
            job_response("analyzing"),
            job_response("analyzing", progress={"done": 1, "total": 2}),
            job_response("analyzing", progress={"done": 2, "total": 2}),
            job_response("summarizing"),
            completed_response(),
        ]
    )
    emitter = FakeEmitter()

    reply = run_pipe(build_pipe(backend), emitter=emitter)

    assert reply == SUMMARY
    assert emitter.descriptions == [
        "Enviando el documento…",
        "En cola…",
        "Extrayendo texto del PDF…",
        "Analizando el documento…",
        "Analizando fragmento 1/2…",
        "Analizando fragmento 2/2…",
        "Redactando el resumen…",
        "Análisis completado",
    ]
    assert [event["data"]["done"] for event in emitter.events] == [False] * 7 + [True]
    assert all(event["type"] == "status" for event in emitter.events)


def test_submission_sends_the_pdf_bytes_question_and_ocr_flag_as_multipart() -> None:
    backend = FakeBackend([completed_response()])

    run_pipe(build_pipe(backend, ocr=True))

    submission = backend.submissions[0]
    body = submission.read()
    assert str(submission.url) == f"{BACKEND_URL}/jobs"
    assert submission.headers["content-type"].startswith("multipart/form-data")
    assert PDF_BYTES in body
    assert b'filename="ley.pdf"' in body
    assert QUESTION.encode() in body
    assert b'name="ocr"\r\n\r\ntrue' in body
    assert str(backend.polls[0].url) == f"{BACKEND_URL}{STATUS_URL}"


def test_request_ignores_the_attached_files_block_added_by_open_webui() -> None:
    backend = FakeBackend([completed_response()])

    run_pipe(build_pipe(backend), metadata={"user_prompt": '<attached_files>\n<file id="file-pdf"/>\n</attached_files>\n\nResume la ley'})

    body = backend.submissions[0].read()
    assert b'name="request"\r\n\r\nResume la ley\r\n' in body
    assert b"attached_files" not in body


def test_request_falls_back_to_the_last_user_message_without_metadata_prompt() -> None:
    backend = FakeBackend([completed_response()])

    run_pipe(build_pipe(backend), metadata={}, question="¿Cuál es el objetivo?")

    assert "¿Cuál es el objetivo?".encode() in backend.submissions[0].read()


def test_completed_job_appends_failed_fragments_and_unverified_facts_notes() -> None:
    notes = [note(0, 1, 1, ["ONU"]), note(1, 3, 4, ["12 %", "DS 004-2020"]), note(2, 5, 6, [])]
    backend = FakeBackend([completed_response(failed_indexes=[7, 9], notes=notes)])

    reply = run_pipe(build_pipe(backend))

    assert reply.startswith(SUMMARY)
    assert "Fragmentos que no se pudieron analizar: 2" in reply
    assert "- Pág. 1: ONU" in reply
    assert "- Págs. 3-4: 12 %, DS 004-2020" in reply
    assert "Págs. 5-6" not in reply


def test_truncated_summary_is_followed_by_a_warning_before_the_other_notes() -> None:
    backend = FakeBackend([completed_response(summary_truncated=True, failed_indexes=[3])])

    reply = run_pipe(build_pipe(backend))

    sections = reply.split("\n\n")
    assert sections[0] == SUMMARY
    assert sections[1] == TRUNCATED_SUMMARY_NOTE
    assert "La respuesta se cortó por su longitud y puede estar incompleta" in TRUNCATED_SUMMARY_NOTE
    assert sections[2].startswith("_Fragmentos que no se pudieron analizar: 1.")


@pytest.mark.parametrize("summary_truncated", [False, None])
def test_complete_or_legacy_summary_has_no_truncation_warning(summary_truncated: bool | None) -> None:
    backend = FakeBackend([completed_response(summary_truncated=summary_truncated)])

    assert run_pipe(build_pipe(backend)) == SUMMARY


def test_unverified_facts_list_is_truncated_with_a_remainder_count() -> None:
    notes = [note(index, index + 1, index + 1, [f"DATO{index}"]) for index in range(7)]
    backend = FakeBackend([completed_response(notes=notes)])

    reply = run_pipe(build_pipe(backend))

    assert "- Pág. 5: DATO4" in reply
    assert "DATO5" not in reply
    assert "Otros fragmentos con datos por verificar: 2." in reply


def test_failed_job_returns_the_backend_error_message() -> None:
    error = api_error(422, "DOCUMENT_WITHOUT_TEXT", "El PDF no tiene texto; prueba con OCR.")
    backend = FakeBackend([job_response("extracting"), job_response("failed", error=error)])
    emitter = FakeEmitter()

    reply = run_pipe(build_pipe(backend), emitter=emitter)

    assert reply == "El PDF no tiene texto; prueba con OCR."
    assert emitter.events[-1]["data"] == {"description": "El análisis falló", "done": True}


@pytest.mark.parametrize(
    "transient_failure",
    [httpx.ConnectError("connection refused"), httpx.ReadTimeout("timed out"), httpx.Response(503, text="unavailable")],
)
def test_transient_polling_failure_reconnects_and_keeps_waiting(transient_failure: Step) -> None:
    backend = FakeBackend([job_response("analyzing"), transient_failure, transient_failure, completed_response()])
    emitter = FakeEmitter()

    reply = run_pipe(build_pipe(backend), emitter=emitter)

    assert reply == SUMMARY
    assert emitter.descriptions.count(RECONNECTING_STATUS) == 1
    assert len(backend.polls) == 4


def test_job_still_running_after_max_wait_explains_how_to_resume() -> None:
    backend = FakeBackend([job_response("analyzing", progress={"done": 1, "total": 9})])
    emitter = FakeEmitter()

    reply = run_pipe(build_pipe(backend, max_wait_seconds=0), emitter=emitter)

    assert reply == STILL_PROCESSING_REPLY
    assert emitter.events[-1]["data"]["done"] is True


def test_job_missing_after_submit_fails_clearly() -> None:
    backend = FakeBackend([httpx.Response(404, json=api_error(404, "JOB_NOT_FOUND", "No existe el trabajo."))])
    emitter = FakeEmitter()

    reply = run_pipe(build_pipe(backend), emitter=emitter)

    assert reply == JOB_NOT_FOUND_REPLY
    assert len(backend.polls) == 1
    assert emitter.events[-1]["data"]["done"] is True


def test_submission_is_retried_after_a_connection_error() -> None:
    backend = FakeBackend([completed_response()], submit_steps=[httpx.ConnectError("refused"), submitted_response(200)])

    reply = run_pipe(build_pipe(backend))

    assert reply == SUMMARY
    assert len(backend.submissions) == 2


def test_submission_gives_up_after_the_maximum_attempts() -> None:
    backend = FakeBackend([completed_response()], submit_steps=[httpx.ConnectError("refused")])

    reply = run_pipe(build_pipe(backend))

    assert reply == SERVICE_UNAVAILABLE_REPLY
    assert len(backend.submissions) == MAX_SUBMIT_ATTEMPTS
    assert backend.polls == []


def test_submission_rejected_by_the_backend_returns_its_message() -> None:
    rejection = httpx.Response(400, json=api_error(400, "EMPTY_FILE", "El archivo está vacío."))
    backend = FakeBackend([completed_response()], submit_steps=[rejection])

    reply = run_pipe(build_pipe(backend))

    assert reply == "El archivo está vacío."
    assert len(backend.submissions) == 1


def test_missing_attachment_asks_for_a_pdf_without_calling_the_backend() -> None:
    backend = FakeBackend([completed_response()])
    emitter = FakeEmitter()

    reply = run_pipe(build_pipe(backend), files=[], emitter=emitter)

    assert reply == MISSING_PDF_REPLY
    assert backend.submissions == []
    assert emitter.events == []


def test_latest_attachment_that_is_not_a_pdf_is_rejected() -> None:
    docx = {"type": "file", "id": "file-docx", "name": "acta.docx", "content_type": "application/msword"}
    backend = FakeBackend([completed_response()])

    reply = run_pipe(build_pipe(backend), files=[PDF_ITEM, docx])

    assert "acta.docx" in reply
    assert "PDF" in reply
    assert backend.submissions == []


def test_the_most_recent_pdf_of_the_chat_is_analyzed() -> None:
    newer = {"type": "file", "id": "file-new", "name": "Anexo.PDF", "content_type": ""}
    image = {"type": "image", "url": "data:image/png;base64,AAAA"}
    store = FakeFileStore({"file-new": StoredFile(owner_id=USER["id"], content=PDF_BYTES)})
    backend = FakeBackend([completed_response()])

    run_pipe(build_pipe(backend, store), files=[PDF_ITEM, newer, image])

    assert store.requested_ids == ["file-new"]
    assert b'filename="Anexo.PDF"' in backend.submissions[0].read()


@pytest.mark.parametrize(
    "stored_files",
    [{}, {"file-pdf": StoredFile(owner_id="someone-else", content=PDF_BYTES)}],
)
def test_unreadable_or_foreign_file_is_not_sent(stored_files: dict[str, StoredFile]) -> None:
    backend = FakeBackend([completed_response()])

    reply = run_pipe(build_pipe(backend, FakeFileStore(stored_files)))

    assert reply == FILE_UNAVAILABLE_REPLY
    assert backend.submissions == []


def test_admin_can_analyze_a_file_uploaded_by_another_user() -> None:
    store = FakeFileStore({"file-pdf": StoredFile(owner_id="someone-else", content=PDF_BYTES)})
    backend = FakeBackend([completed_response()])
    pipe = build_pipe(backend, store)

    reply = asyncio.run(
        pipe.pipe({"messages": [{"role": "user", "content": QUESTION}]}, __user__={"id": "admin-1", "role": "admin"}, __files__=[PDF_ITEM])
    )

    assert reply == SUMMARY


def test_background_tasks_never_submit_jobs() -> None:
    backend = FakeBackend([completed_response()])

    reply = run_pipe(build_pipe(backend), task="title_generation")

    assert reply == ""
    assert backend.submissions == []


def test_runs_without_an_event_emitter() -> None:
    backend = FakeBackend([job_response("queued"), completed_response()])

    assert run_pipe(build_pipe(backend), emitter=None) == SUMMARY


def analyzing_steps(total: int) -> list[httpx.Response]:
    return [job_response("analyzing", progress={"done": done, "total": total}) for done in range(1, total + 1)]


def test_analyzing_progress_is_reported_on_the_first_unit_each_ten_percent_and_the_last_unit() -> None:
    backend = FakeBackend([job_response("analyzing"), *analyzing_steps(109), job_response("summarizing"), completed_response()])
    emitter = FakeEmitter()

    run_pipe(build_pipe(backend), emitter=emitter)

    reported = [1, 11, 22, 33, 44, 55, 66, 77, 88, 99, 109]
    assert emitter.descriptions == [
        "Enviando el documento…",
        "Analizando el documento…",
        *[f"Analizando fragmento {done}/109…" for done in reported],
        "Redactando el resumen…",
        "Análisis completado",
    ]


def test_summarizing_reports_each_part_of_every_reduction_round() -> None:
    rounds = [(done, total) for total in (4, 1) for done in range(1, total + 1)]
    steps = [job_response("summarizing", progress={"done": done, "total": total}) for done, total in rounds]
    backend = FakeBackend([job_response("summarizing"), *steps, completed_response()])
    emitter = FakeEmitter()

    run_pipe(build_pipe(backend), emitter=emitter)

    assert emitter.descriptions == [
        "Enviando el documento…",
        "Redactando el resumen…",
        "Redactando el resumen: parte 1/4…",
        "Redactando el resumen: parte 2/4…",
        "Redactando el resumen: parte 3/4…",
        "Redactando el resumen: parte 4/4…",
        "Redactando el resumen: parte 1/1…",
        "Análisis completado",
    ]


def test_a_new_reduction_round_is_reported_from_its_first_part() -> None:
    first_round = [job_response("summarizing", progress={"done": done, "total": 45}) for done in range(1, 46)]
    backend = FakeBackend([*first_round, job_response("summarizing", progress={"done": 1, "total": 12}), completed_response()])
    emitter = FakeEmitter()

    run_pipe(build_pipe(backend), emitter=emitter)

    assert emitter.descriptions[1] == "Redactando el resumen: parte 1/45…"
    assert emitter.descriptions[-3:] == ["Redactando el resumen: parte 45/45…", "Redactando el resumen: parte 1/12…", "Análisis completado"]
    assert len(emitter.descriptions) == 14


def test_restarted_stage_is_reported_again_from_its_first_unit() -> None:
    backend = FakeBackend(
        [
            *analyzing_steps(20)[:15],
            job_response("queued"),
            job_response("analyzing", progress={"done": 1, "total": 20}),
            completed_response(),
        ]
    )
    emitter = FakeEmitter()

    run_pipe(build_pipe(backend), emitter=emitter)

    assert emitter.descriptions[-3:] == ["En cola…", "Analizando fragmento 1/20…", "Análisis completado"]
