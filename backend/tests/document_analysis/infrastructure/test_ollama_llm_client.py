from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from ollama import ResponseError

from src.document_analysis.domain.models import ChatMessage, GenerationOptions
from src.document_analysis.domain.ports import LLMClient
from src.document_analysis.infrastructure.llm.ollama_llm_client import OllamaLlmClient
from src.shared.enums.error_code import ErrorCode
from src.shared.enums.message_role import MessageRole
from src.shared.errors.llm_unavailable_error import LlmUnavailableError

OPTIONS = GenerationOptions(model="modelo-x", num_ctx=4096, temperature=0.3, top_p=0.8, keep_alive="10m", max_output_tokens=256)
MESSAGES = [ChatMessage(MessageRole.SYSTEM, "reglas"), ChatMessage(MessageRole.USER, "pregunta")]


class FakeChat:
    def __init__(self, reply: str | None = "respuesta", failure: Exception | None = None) -> None:
        self.reply = reply
        self.failure = failure
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return SimpleNamespace(message=SimpleNamespace(content=self.reply))


def test_returns_the_model_answer():
    assert OllamaLlmClient(FakeChat("hola")).generate(MESSAGES, OPTIONS) == "hola"


def test_sends_model_messages_and_options_from_the_profile():
    fake = FakeChat()
    OllamaLlmClient(fake).generate(MESSAGES, OPTIONS)
    call = fake.calls[0]
    assert call["model"] == "modelo-x"
    assert call["messages"] == [{"role": "system", "content": "reglas"}, {"role": "user", "content": "pregunta"}]
    assert call["options"] == {"num_ctx": 4096, "temperature": 0.3, "top_p": 0.8, "num_predict": 256}
    assert call["keep_alive"] == "10m"
    assert call["stream"] is False


def test_empty_content_becomes_empty_string():
    assert OllamaLlmClient(FakeChat(reply=None)).generate(MESSAGES, OPTIONS) == ""


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
