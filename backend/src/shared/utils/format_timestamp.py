from datetime import datetime

from src.shared.constants.formats import TIMESTAMP_FORMAT


def format_timestamp(moment: datetime) -> str:
    return moment.strftime(TIMESTAMP_FORMAT)
