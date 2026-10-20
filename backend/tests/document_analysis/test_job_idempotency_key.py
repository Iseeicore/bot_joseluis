import hashlib
import json
from dataclasses import replace

import pytest

from src.document_analysis.application.job_idempotency_key import JobIdentity, job_idempotency_key, normalize_request
from src.document_analysis.domain.models import GenerationOptions
from src.shared.constants.regex.note_facts import FINGERPRINT_PATTERN
from src.shared.constants.texts.jobs import DEFAULT_JOB_REQUEST_TEXT

NOTES_OPTIONS = GenerationOptions(
    model="m4", num_ctx=8192, temperature=0.2, top_p=0.9, keep_alive="30m", max_output_tokens=1024, think=False
)
SUMMARY_OPTIONS = replace(NOTES_OPTIONS, model="m9")
IDENTITY = JobIdentity(
    notes_prompt="NOTAS",
    summary_prompt="RESUMEN",
    notes_options=NOTES_OPTIONS,
    summary_options=SUMMARY_OPTIONS,
    summary_batch_chars=15000,
)
SHA = "a" * 64


@pytest.mark.parametrize("value", [None, "", "   \n"])
def test_missing_or_blank_request_becomes_the_default_request(value: str | None):
    assert normalize_request(value) == DEFAULT_JOB_REQUEST_TEXT == "Resume el documento"


def test_request_is_stripped():
    assert normalize_request("  ¿Qué plazo fija la norma?  ") == "¿Qué plazo fija la norma?"


def test_key_is_the_sha256_of_the_documented_json_list():
    expected_identity = [
        SHA,
        "pregunta",
        True,
        "NOTAS",
        "RESUMEN",
        ["m4", 8192, 0.2, 0.9, "30m", 1024, False],
        ["m9", 8192, 0.2, 0.9, "30m", 1024, False],
        15000,
    ]
    expected = hashlib.sha256(json.dumps(expected_identity, ensure_ascii=False).encode("utf-8")).hexdigest()
    key = job_idempotency_key(SHA, "pregunta", True, IDENTITY)
    assert key == expected
    assert FINGERPRINT_PATTERN.fullmatch(key)


def test_same_inputs_give_the_same_key():
    assert job_idempotency_key(SHA, "pregunta", False, IDENTITY) == job_idempotency_key(SHA, "pregunta", False, IDENTITY)


@pytest.mark.parametrize(
    ("sha", "request_text", "ocr", "identity"),
    [
        ("b" * 64, "pregunta", False, IDENTITY),
        (SHA, "otra pregunta", False, IDENTITY),
        (SHA, "pregunta", True, IDENTITY),
        (SHA, "pregunta", False, replace(IDENTITY, notes_prompt="NOTAS v2")),
        (SHA, "pregunta", False, replace(IDENTITY, summary_prompt="RESUMEN v2")),
        (SHA, "pregunta", False, replace(IDENTITY, notes_options=replace(NOTES_OPTIONS, think=True))),
        (SHA, "pregunta", False, replace(IDENTITY, summary_options=replace(SUMMARY_OPTIONS, temperature=0.5))),
        (SHA, "pregunta", False, replace(IDENTITY, summary_options=replace(SUMMARY_OPTIONS, max_output_tokens=2048))),
        (SHA, "pregunta", False, replace(IDENTITY, summary_batch_chars=6000)),
    ],
)
def test_any_component_change_gives_a_different_key(sha: str, request_text: str, ocr: bool, identity: JobIdentity):
    assert job_idempotency_key(sha, request_text, ocr, identity) != job_idempotency_key(SHA, "pregunta", False, IDENTITY)
