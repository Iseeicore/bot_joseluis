from src.document_analysis.domain.models import GenerationOptions
from src.shared.config.settings import ModelProfile


def to_generation_options(profile: ModelProfile) -> GenerationOptions:
    return GenerationOptions(
        model=profile.model,
        num_ctx=profile.num_ctx,
        temperature=profile.temperature,
        top_p=profile.top_p,
        keep_alive=profile.keep_alive,
        max_output_tokens=profile.max_output_tokens,
        think=profile.think,
    )
