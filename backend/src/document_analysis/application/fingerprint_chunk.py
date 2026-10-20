import hashlib
import json

from src.document_analysis.domain.models import GenerationOptions


def fingerprint_chunk(chunk_text: str, notes_prompt: str, options: GenerationOptions) -> str:
    identity = [chunk_text, notes_prompt, options.model, options.temperature, options.top_p, options.max_output_tokens, options.think]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()
