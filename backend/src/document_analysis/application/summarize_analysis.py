from dataclasses import dataclass

from src.document_analysis.application.build_analysis_messages import build_summary_messages
from src.document_analysis.application.progress import ProgressCallback, ignore_progress
from src.document_analysis.domain.models import DocumentAnalysis, Generation, GenerationOptions
from src.document_analysis.domain.ports import LLMClient
from src.shared.constants.prompts.analysis import NO_CONTENT_NOTE_TEXT, pages_label
from src.shared.constants.texts.llm import NO_NOTES_ANSWER_TEXT
from src.shared.errors.empty_model_answer_error import EmptyModelAnswerError

ITEM_SEPARATOR = "\n\n"
MIN_ITEMS_PER_BATCH = 2


@dataclass(frozen=True)
class SummarySetup:
    llm: LLMClient
    summary_prompt: str
    options: GenerationOptions
    batch_chars: int


@dataclass(frozen=True)
class SummaryItem:
    first_page: int
    last_page: int
    text: str
    truncated: bool = False

    def render(self) -> str:
        return f"{pages_label(self.first_page, self.last_page)}\n{self.text}"


def batch_items(items: list[SummaryItem], batch_chars: int) -> list[list[SummaryItem]]:
    batches: list[list[SummaryItem]] = [[]]
    size = 0
    for item in items:
        length = len(item.render())
        if len(batches[-1]) >= MIN_ITEMS_PER_BATCH and size + length > batch_chars:
            batches.append([])
            size = 0
        batches[-1].append(item)
        size += length
    return batches


def reduce_batch(batch: list[SummaryItem], request: str, setup: SummarySetup, position: int) -> SummaryItem:
    notes_text = ITEM_SEPARATOR.join(item.render() for item in batch)
    generation = setup.llm.generate(build_summary_messages(setup.summary_prompt, request, notes_text), setup.options)
    answer = generation.text.strip()
    if not answer:
        raise EmptyModelAnswerError(setup.options.model, position)
    return SummaryItem(batch[0].first_page, batch[-1].last_page, answer, generation.truncated)


def reduce_round(batches: list[list[SummaryItem]], request: str, setup: SummarySetup, on_progress: ProgressCallback) -> list[SummaryItem]:
    reduced: list[SummaryItem] = []
    for position, batch in enumerate(batches):
        reduced.append(reduce_batch(batch, request, setup, position))
        on_progress(len(reduced), len(batches))
    return reduced


def summarize_analysis(
    analysis: DocumentAnalysis, request: str, setup: SummarySetup, on_progress: ProgressCallback = ignore_progress
) -> Generation:
    items = [
        SummaryItem(note.first_page, note.last_page, note.text)
        for note in analysis.notes
        if note.index not in analysis.failed_indexes and note.text.strip() != NO_CONTENT_NOTE_TEXT
    ]
    if not items:
        return Generation(text=NO_NOTES_ANSWER_TEXT, truncated=False)
    batches = batch_items(items, setup.batch_chars)
    while len(batches) > 1:
        batches = batch_items(reduce_round(batches, request, setup, on_progress), setup.batch_chars)
    final = reduce_round(batches, request, setup, on_progress)[0]
    return Generation(text=final.text, truncated=final.truncated)
