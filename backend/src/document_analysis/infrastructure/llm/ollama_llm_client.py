import logging
from typing import Any, Protocol

import httpx
from ollama import ResponseError

from src.document_analysis.domain.models import ChatMessage, Generation, GenerationOptions
from src.shared.enums.ollama_done_reason import OllamaDoneReason
from src.shared.errors.llm_unavailable_error import LlmUnavailableError

logger = logging.getLogger(__name__)


class OllamaChat(Protocol):
    def chat(self, **kwargs: Any) -> Any: ...


def warn_if_context_is_full(response: Any, options: GenerationOptions) -> None:
    if response.prompt_eval_count is None:
        return
    used_tokens = response.prompt_eval_count + (response.eval_count or 0)
    if used_tokens < options.num_ctx:
        return
    logger.warning(
        "Model %s filled its context window: prompt_eval_count=%s eval_count=%s num_ctx=%s",
        options.model,
        response.prompt_eval_count,
        response.eval_count,
        options.num_ctx,
        extra={
            "model": options.model,
            "prompt_eval_count": response.prompt_eval_count,
            "eval_count": response.eval_count,
            "num_ctx": options.num_ctx,
        },
    )


def is_truncated(response: Any) -> bool:
    return response.done_reason == OllamaDoneReason.LENGTH


def warn_if_truncated(response: Any, options: GenerationOptions) -> None:
    if not is_truncated(response):
        return
    logger.warning(
        "Model %s stopped at its output limit: eval_count=%s num_predict=%s",
        options.model,
        response.eval_count,
        options.max_output_tokens,
        extra={"model": options.model, "eval_count": response.eval_count, "num_predict": options.max_output_tokens},
    )


class OllamaLlmClient:
    def __init__(self, client: OllamaChat) -> None:
        self.client = client

    def generate(self, messages: list[ChatMessage], options: GenerationOptions) -> Generation:
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
                think=options.think,
                stream=False,
            )
        except (ConnectionError, ResponseError, httpx.TransportError) as error:
            raise LlmUnavailableError(options.model) from error
        warn_if_context_is_full(response, options)
        warn_if_truncated(response, options)
        return Generation(text=response.message.content or "", truncated=is_truncated(response))
