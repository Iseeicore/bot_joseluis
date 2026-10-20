import argparse
import json
import sys
import time
from pathlib import Path

from ollama import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.app.generation_options import to_generation_options
from src.document_analysis.application.analyze_document import AnalysisSetup, analyze_document
from src.document_analysis.application.summarize_analysis import SummarySetup, summarize_analysis
from src.document_analysis.infrastructure.chunking.recursive_text_chunker import RecursiveTextChunker
from src.document_analysis.infrastructure.extractors.pdf_text_extractor import PdfTextExtractor
from src.document_analysis.infrastructure.llm.ollama_llm_client import OllamaLlmClient
from src.document_analysis.infrastructure.ocr.rapid_ocr_engine import RapidOcrEngine
from src.document_analysis.infrastructure.storage.json_notes_store import JsonNotesStore
from src.shared.config.settings import load_settings
from src.shared.config.system_prompt import load_prompt_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--summary", default=None)
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--summary-profile", default=None)
    args = parser.parse_args()

    settings = load_settings()
    profile = settings.active
    options = to_generation_options(profile)
    llm = OllamaLlmClient(Client(host=settings.ollama.base_url, timeout=settings.ollama.timeout_seconds))
    store = JsonNotesStore(args.store or settings.notes_dir_path)

    started = time.time()
    document = PdfTextExtractor(RapidOcrEngine() if args.ocr else None).extract(args.pdf.read_bytes(), args.pdf.name)
    extraction_seconds = time.time() - started
    print(f"extracted {len(document.pages)} pages in {extraction_seconds:.0f}s (scanned={len(document.scanned_page_numbers)})", flush=True)

    setup = AnalysisSetup(
        RecursiveTextChunker(profile.chunk_size_chars, profile.chunk_overlap_chars),
        llm,
        store,
        load_prompt_file(settings.notes_prompt_path),
        options,
    )
    last = [time.time()]

    def progress(done: int, total: int) -> None:
        now = time.time()
        print(f"chunk {done}/{total} +{now - last[0]:.0f}s", flush=True)
        last[0] = now

    started = time.time()
    analysis = analyze_document(document, setup, progress)
    analysis_seconds = time.time() - started
    flagged = [note for note in analysis.notes if note.unverified_facts]
    report = {
        "model": options.model,
        "pages": len(document.pages),
        "chunks": len(analysis.notes),
        "generated": analysis.generated_count,
        "reused": analysis.reused_count,
        "analysis_seconds": round(analysis_seconds),
        "notes_with_unverified_facts": len(flagged),
        "unverified_total": sum(len(note.unverified_facts) for note in analysis.notes),
        "failed_chunks": list(analysis.failed_indexes),
        "note_chars": sum(len(note.text) for note in analysis.notes),
    }
    if args.summary:
        started = time.time()
        summary_profile = settings.profiles[args.summary_profile] if args.summary_profile else settings.summary
        summary_setup = SummarySetup(
            llm, load_prompt_file(settings.summary_prompt_path), to_generation_options(summary_profile), summary_profile.chunk_size_chars
        )
        summary = summarize_analysis(analysis, args.summary, summary_setup)
        report["summary"] = summary.text
        report["summary_truncated"] = summary.truncated
        report["summary_seconds"] = round(time.time() - started)
    report["flagged_examples"] = [{"pages": [n.first_page, n.last_page], "facts": list(n.unverified_facts)[:6]} for n in flagged[:15]]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.report:
        args.report.write_text(
            json.dumps({**report, "notes": [vars(note) for note in analysis.notes]}, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
