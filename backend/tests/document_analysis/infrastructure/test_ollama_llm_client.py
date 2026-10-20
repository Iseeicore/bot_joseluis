import logging
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from ollama import ResponseError

from src.document_analysis.domain.models import ChatMessage, Generation, GenerationOptions
from src.document_analysis.domain.ports import LLMClient
from src.document_analysis.infrastructure.llm import ollama_llm_client
from src.document_analysis.infrastructure.llm.ollama_llm_client import OllamaLlmClient
from src.shared.enums.error_code import ErrorCode
from src.shared.enums.message_role import MessageRole
from src.shared.errors.llm_unavailable_error import LlmUnavailableError

OPTIONS = GenerationOptions(
    model="modelo-x", num_ctx=4096, temperature=0.3, top_p=0.8, keep_alive="10m", max_output_tokens=256, think=False
)
MESSAGES = [ChatMessage(MessageRole.SYSTEM, "reglas"), ChatMessage(MessageRole.USER, "pregunta")]


class FakeChat:
    def __init__(
        self,
        reply: str | None = "respuesta",
        failure: Exception | None = None,
        prompt_eval_count: int | None = None,
        eval_count: int | None = None,
        done_reason: str | None = "stop",
    ) -> None:
        self.reply = reply
        self.failure = failure
        self.prompt_eval_count = prompt_eval_count
        self.eval_count = eval_count
        self.done_reason = done_reason
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return SimpleNamespace(
            message=SimpleNamespace(content=self.reply),
            prompt_eval_count=self.prompt_eval_count,
            eval_count=self.eval_count,
            done_reason=self.done_reason,
        )


def generate_logging(fake: FakeChat, caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    with caplog.at_level(logging.WARNING, logger=ollama_llm_client.__name__):
        OllamaLlmClient(fake).generate(MESSAGES, OPTIONS)
    return [record for record in caplog.records if record.name == ollama_llm_client.__name__]


def test_returns_the_model_answer():
    assert OllamaLlmClient(FakeChat("hola")).generate(MESSAGES, OPTIONS) == Generation(text="hola", truncated=False)


def test_answer_stopped_by_the_output_limit_is_marked_truncated():
    generation = OllamaLlmClient(FakeChat("respuesta cortada", done_reason="length")).generate(MESSAGES, OPTIONS)
    assert generation == Generation(text="respuesta cortada", truncated=True)


@pytest.mark.parametrize("done_reason", ["stop", None])
def test_answer_that_ended_on_its_own_is_not_truncated(done_reason: str | None):
    assert OllamaLlmClient(FakeChat(done_reason=done_reason)).generate(MESSAGES, OPTIONS).truncated is False


def test_warns_when_the_answer_is_truncated(caplog: pytest.LogCaptureFixture):
    records = generate_logging(FakeChat(reply="respuesta secreta", eval_count=256, done_reason="length"), caplog)
    assert [record.levelno for record in records] == [logging.WARNING]
    record = records[0]
    assert (record.model, record.eval_count, record.num_predict) == ("modelo-x", 256, 256)
    assert "modelo-x" in record.getMessage()
    assert "256" in record.getMessage()
    assert "respuesta secreta" not in record.getMessage()
    assert "pregunta" not in record.getMessage()


def test_does_not_warn_when_the_answer_ended_on_its_own(caplog: pytest.LogCaptureFixture):
    assert generate_logging(FakeChat(eval_count=256, done_reason="stop"), caplog) == []


def test_sends_model_messages_and_options_from_the_profile():
    fake = FakeChat()
    OllamaLlmClient(fake).generate(MESSAGES, OPTIONS)
    call = fake.calls[0]
    assert call["model"] == "modelo-x"
    assert call["messages"] == [{"role": "system", "content": "reglas"}, {"role": "user", "content": "pregunta"}]
    assert call["options"] == {"num_ctx": 4096, "temperature": 0.3, "top_p": 0.8, "num_predict": 256}
    assert call["keep_alive"] == "10m"
    assert call["stream"] is False
    assert call["think"] is False


def test_sends_the_think_mode_of_the_profile():
    fake = FakeChat()
    OllamaLlmClient(fake).generate(MESSAGES, GenerationOptions(**{**vars(OPTIONS), "think": True}))
    assert fake.calls[0]["think"] is True


def test_empty_content_becomes_empty_string():
    assert OllamaLlmClient(FakeChat(reply=None)).generate(MESSAGES, OPTIONS).text == ""


@pytest.mark.parametrize(
    "failure",
    [ConnectionError("down"), ResponseError("model not found", 404), httpx.ReadTimeout("slow"), httpx.RemoteProtocolError("closed")],
)
def test_transport_failures_become_llm_unavailable(failure):
    with pytest.raises(LlmUnavailableError) as raised:
        OllamaLlmClient(FakeChat(failure=failure)).generate(MESSAGES, OPTIONS)
    assert raised.value.status_code == 503
    assert raised.value.error_code == ErrorCode.LLM_UNAVAILABLE
    assert raised.value.model == "modelo-x"


def test_unexpected_errors_are_not_swallowed():
    with pytest.raises(KeyError):
        OllamaLlmClient(FakeChat(failure=KeyError("bug"))).generate(MESSAGES, OPTIONS)


def test_satisfies_the_llm_port():
    assert isinstance(OllamaLlmClient(FakeChat()), LLMClient)


def test_warns_when_prompt_and_answer_fill_the_context_window(caplog: pytest.LogCaptureFixture):
    records = generate_logging(FakeChat(prompt_eval_count=4000, eval_count=96), caplog)
    assert [record.levelno for record in records] == [logging.WARNING]
    record = records[0]
    assert (record.model, record.prompt_eval_count, record.eval_count, record.num_ctx) == ("modelo-x", 4000, 96, 4096)
    assert "modelo-x" in record.getMessage()
    assert "4000" in record.getMessage()
    assert "4096" in record.getMessage()


def test_warns_when_the_prompt_alone_fills_the_context_window(caplog: pytest.LogCaptureFixture):
    records = generate_logging(FakeChat(prompt_eval_count=4096), caplog)
    assert len(records) == 1
    assert records[0].eval_count is None


def test_does_not_warn_below_the_context_window(caplog: pytest.LogCaptureFixture):
    assert generate_logging(FakeChat(prompt_eval_count=3000, eval_count=1095), caplog) == []


def test_does_not_warn_without_the_prompt_token_count(caplog: pytest.LogCaptureFixture):
    assert generate_logging(FakeChat(eval_count=5000), caplog) == []


def test_context_warning_does_not_include_the_conversation(caplog: pytest.LogCaptureFixture):
    records = generate_logging(FakeChat(reply="respuesta secreta", prompt_eval_count=4096), caplog)
    assert "pregunta" not in records[0].getMessage()
    assert "respuesta secreta" not in records[0].getMessage()
