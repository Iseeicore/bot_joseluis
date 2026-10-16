from typing import Any, Protocol

import httpx
from ollama import ResponseError

from src.document_analysis.domain.models import ChatMessage, GenerationOptions
from src.shared.errors.llm_unavailable_error import LlmUnavailableError


class OllamaChat(Protocol):
    def chat(self, **kwargs: Any) -> Any: ...


class OllamaLlmClient:
    def __init__(self, client: OllamaChat) -> None:
        self.client = client

    def generate(self, messages: list[ChatMessage], options: GenerationOptions) -> str:
        try:
            response = self.client.chat(
                model=options.model,
                messages=[{"role": message.role.value, "content": message.content} for message in messages],
                options={
                    "num_ctx": options.num_ctx,
                    "temperature": options.temperature,
                    "top_p": options.top_p,
                    "num_predict": options.max_output_tokens,
                },
                keep_alive=options.keep_alive,
                stream=False,
            )
        except (ConnectionError, ResponseError, httpx.TransportError) as error:
            raise LlmUnavailableError(options.model) from error
        return response.message.content or ""
