from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class JobNote(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    index: int
    first_page: int
    last_page: int
    text: str
    unverified_facts: list[str]


class JobResult(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    summary: str
    summary_truncated: bool = False
    notes: list[JobNote]
    generated_count: int
    reused_count: int
    failed_indexes: list[int]
    scanned_pages: list[int]
