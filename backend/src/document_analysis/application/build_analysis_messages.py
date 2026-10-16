from src.document_analysis.domain.models import ChatMessage
from src.shared.constants.prompts.analysis import (
    REMOVED_TAG_TEXT,
    notes_user_message_text,
    summary_user_message_text,
    user_message_text,
)
from src.shared.constants.regex.prompt_tags import PROMPT_TAG_PATTERN
from src.shared.enums.message_role import MessageRole


def neutralize_tags(text: str) -> str:
    return PROMPT_TAG_PATTERN.sub(REMOVED_TAG_TEXT, text)


def build_analysis_messages(system_prompt: str, request: str, document_text: str) -> list[ChatMessage]:
    user_text = user_message_text(neutralize_tags(request), neutralize_tags(document_text))
    return [
        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
        ChatMessage(role=MessageRole.USER, content=user_text),
    ]


def build_notes_messages(notes_prompt: str, chunk_text: str) -> list[ChatMessage]:
    return [
        ChatMessage(role=MessageRole.SYSTEM, content=notes_prompt),
        ChatMessage(role=MessageRole.USER, content=notes_user_message_text(neutralize_tags(chunk_text))),
    ]


def build_summary_messages(summary_prompt: str, request: str, notes_text: str) -> list[ChatMessage]:
    user_text = summary_user_message_text(neutralize_tags(request), neutralize_tags(notes_text))
    return [
        ChatMessage(role=MessageRole.SYSTEM, content=summary_prompt),
        ChatMessage(role=MessageRole.USER, content=user_text),
    ]
