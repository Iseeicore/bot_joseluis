from enum import StrEnum


class OllamaDoneReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
