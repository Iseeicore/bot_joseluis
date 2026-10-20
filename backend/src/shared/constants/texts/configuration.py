from pathlib import Path

from src.shared.constants.limits.model_context import CONSERVATIVE_CHARS_PER_TOKEN


def missing_config_file_text(config_file: Path) -> str:
    return f"No existe el archivo de configuración: {config_file}"


def invalid_config_text(detail: str) -> str:
    return f"La configuración no es válida: {detail}"


def unknown_profile_text(profile: str, available: list[str]) -> str:
    return f'El perfil "{profile}" no existe. Perfiles disponibles: {", ".join(sorted(available))}'


def overlap_too_large_text(overlap: int, size: int) -> str:
    return f"chunk_overlap_chars ({overlap}) debe ser menor que chunk_size_chars ({size})"


def summary_batch_too_large_text(batch_chars: int, limit: int) -> str:
    return (
        f"summary_batch_chars ({batch_chars}) debe ser como máximo {limit}: "
        f"(num_ctx - max_output_tokens) × {CONSERVATIVE_CHARS_PER_TOKEN} caracteres por token"
    )


def missing_prompt_file_text(prompt_file: Path) -> str:
    return f"No existe el archivo de prompt: {prompt_file}"


def empty_prompt_file_text(prompt_file: Path) -> str:
    return f"El archivo de prompt está vacío: {prompt_file}"
