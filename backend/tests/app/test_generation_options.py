from src.app.generation_options import to_generation_options
from src.document_analysis.domain.models import GenerationOptions
from src.shared.config.settings import ModelProfile


def test_maps_every_generation_field_from_the_profile():
    profile = ModelProfile(
        model="qwen2.5:7b",
        num_ctx=4096,
        temperature=0.3,
        top_p=0.8,
        keep_alive="10m",
        chunk_size_chars=5000,
        chunk_overlap_chars=200,
        max_output_tokens=512,
    )
    assert to_generation_options(profile) == GenerationOptions(
        model="qwen2.5:7b",
        num_ctx=4096,
        temperature=0.3,
        top_p=0.8,
        keep_alive="10m",
        max_output_tokens=512,
    )
