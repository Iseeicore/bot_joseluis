from dataclasses import dataclass, replace

from src.document_analysis.application.build_analysis_messages import build_notes_messages
from src.document_analysis.application.chunk_document import chunk_document
from src.document_analysis.application.fingerprint_chunk import fingerprint_chunk
from src.document_analysis.application.progress import ProgressCallback, ignore_progress
from src.document_analysis.application.verify_note_facts import find_unverified_facts
from src.document_analysis.domain.models import ChunkNote, DocumentAnalysis, DocumentChunk, ExtractedDocument, GenerationOptions
from src.document_analysis.domain.ports import Chunker, LLMClient, NotesStore
from src.shared.constants.limits.note_facts import MAX_NOTE_ATTEMPTS, MIN_NOTE_ALPHANUMERIC_CHARS, RETRY_TEMPERATURE_STEP
from src.shared.constants.prompts.analysis import UNREADABLE_NOTE_TEXT
from src.shared.constants.regex.note_facts import ALPHANUMERIC_CHAR_PATTERN
from src.shared.enums.note_origin import NoteOrigin
from src.shared.errors.empty_model_answer_error import EmptyModelAnswerError


@dataclass(frozen=True)
class AnalysisSetup:
    chunker: Chunker
    llm: LLMClient
    store: NotesStore
    notes_prompt: str
    options: GenerationOptions


def is_usable(answer: str) -> bool:
    return len(ALPHANUMERIC_CHAR_PATTERN.findall(answer)) >= MIN_NOTE_ALPHANUMERIC_CHARS


def generate_note(chunk: DocumentChunk, setup: AnalysisSetup) -> ChunkNote | None:
    messages = build_notes_messages(setup.notes_prompt, chunk.text)
    for attempt in range(MAX_NOTE_ATTEMPTS):
        options = replace(setup.options, temperature=setup.options.temperature + attempt * RETRY_TEMPERATURE_STEP)
        answer = setup.llm.generate(messages, options).text.strip()
        if is_usable(answer):
            return ChunkNote(chunk.index, chunk.first_page, chunk.last_page, answer, find_unverified_facts(answer, chunk.text))
    return None


def unreadable_note(chunk: DocumentChunk) -> ChunkNote:
    return ChunkNote(chunk.index, chunk.first_page, chunk.last_page, UNREADABLE_NOTE_TEXT, ())


def resolve_note(chunk: DocumentChunk, setup: AnalysisSetup) -> tuple[ChunkNote, NoteOrigin]:
    fingerprint = fingerprint_chunk(chunk.text, setup.notes_prompt, setup.options)
    stored = setup.store.load(fingerprint)
    if stored is not None:
        return replace(stored, index=chunk.index, first_page=chunk.first_page, last_page=chunk.last_page), NoteOrigin.REUSED
    generated = generate_note(chunk, setup)
    if generated is None:
        return unreadable_note(chunk), NoteOrigin.FAILED
    setup.store.save(fingerprint, generated)
    return generated, NoteOrigin.GENERATED


def analyze_document(
    document: ExtractedDocument, setup: AnalysisSetup, on_progress: ProgressCallback = ignore_progress
) -> DocumentAnalysis:
    chunks = chunk_document(document, setup.chunker)
    resolved: list[tuple[ChunkNote, NoteOrigin]] = []
    for chunk in chunks:
        resolved.append(resolve_note(chunk, setup))
        on_progress(len(resolved), len(chunks))
    origins = [origin for _, origin in resolved]
    failed = tuple(note.index for note, origin in resolved if origin == NoteOrigin.FAILED)
    if chunks and len(failed) == len(chunks):
        raise EmptyModelAnswerError(setup.options.model, failed[0])
    return DocumentAnalysis(
        name=document.name,
        notes=tuple(note for note, _ in resolved),
        generated_count=origins.count(NoteOrigin.GENERATED),
        reused_count=origins.count(NoteOrigin.REUSED),
        failed_indexes=failed,
    )
