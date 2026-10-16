import statistics
from dataclasses import dataclass
from itertools import pairwise

from src.shared.constants.limits.ocr_layout import (
    HEADER_BAND_MARGIN,
    HEADER_WIDTH_TOLERANCE,
    MARK_MAX_CHARS,
    MIN_COLUMN_HEADERS,
    MIN_COLUMN_TOLERANCE,
    ROTATED_ASPECT_RATIO,
    ROTATED_MIN_CHARS,
    ROW_TOLERANCE,
    SHORT_HEADER_MIN_ASPECT,
)
from src.shared.constants.prompts.analysis import columns_line_text, marked_row_text


@dataclass(frozen=True)
class OcrFragment:
    text: str
    x_center: float
    y_center: float
    width: float
    height: float


def is_confident_header(fragment: OcrFragment) -> bool:
    return fragment.height > ROTATED_ASPECT_RATIO * fragment.width and len(fragment.text) >= ROTATED_MIN_CHARS


def is_short_header(fragment: OcrFragment, line_width: float) -> bool:
    similar_width = abs(fragment.width - line_width) <= HEADER_WIDTH_TOLERANCE * line_width
    return similar_width and fragment.height > SHORT_HEADER_MIN_ASPECT * fragment.width


def distinct_columns(headers: list[OcrFragment]) -> int:
    positions = sorted(header.x_center for header in headers)
    return min(len(positions), 1) + sum(1 for left, right in pairwise(positions) if right - left > MIN_COLUMN_TOLERANCE)


def find_headers(fragments: list[OcrFragment]) -> list[OcrFragment]:
    seeds = [fragment for fragment in fragments if is_confident_header(fragment)]
    if distinct_columns(seeds) < MIN_COLUMN_HEADERS:
        return []
    line_width = statistics.median(seed.width for seed in seeds)
    band_top = min(seed.y_center for seed in seeds) - HEADER_BAND_MARGIN
    band_bottom = max(seed.y_center for seed in seeds) + HEADER_BAND_MARGIN
    in_band = (fragment for fragment in fragments if band_top <= fragment.y_center <= band_bottom)
    found = [fragment for fragment in in_band if fragment in seeds or is_short_header(fragment, line_width)]
    return sorted(found, key=lambda item: item.x_center)


def group_rows(fragments: list[OcrFragment]) -> list[list[OcrFragment]]:
    rows: list[list[OcrFragment]] = []
    row_y = 0.0
    for fragment in sorted(fragments, key=lambda item: item.y_center):
        if not rows or abs(fragment.y_center - row_y) > ROW_TOLERANCE:
            rows.append([])
        rows[-1].append(fragment)
        row_y = statistics.mean(item.y_center for item in rows[-1])
    return [sorted(row, key=lambda item: item.x_center) for row in rows]


def column_tolerance(headers: list[OcrFragment]) -> float:
    gaps = [right.x_center - left.x_center for left, right in pairwise(headers)]
    return max(statistics.median(gaps) / 2, MIN_COLUMN_TOLERANCE)


def nearest_column(mark: OcrFragment, headers: list[OcrFragment], tolerance: float) -> OcrFragment | None:
    closest = min(headers, key=lambda header: abs(header.x_center - mark.x_center))
    return closest if abs(closest.x_center - mark.x_center) <= tolerance else None


def render_row(row: list[OcrFragment], headers: list[OcrFragment], tolerance: float) -> str:
    labels: list[str] = []
    columns: list[str] = []
    for cell in row:
        column = nearest_column(cell, headers, tolerance) if len(cell.text.strip()) <= MARK_MAX_CHARS else None
        if column is None:
            labels.append(cell.text)
        else:
            columns.append(column.text)
    return marked_row_text(" ".join(labels), columns) if columns else " ".join(labels)


def layout_ocr_text(fragments: list[OcrFragment]) -> str:
    headers = find_headers(fragments)
    if not headers:
        return "\n".join(fragment.text for fragment in fragments)
    tolerance = column_tolerance(headers)
    body = [fragment for fragment in fragments if fragment not in headers]
    rows = [render_row(row, headers, tolerance) for row in group_rows(body)]
    return "\n".join([columns_line_text([header.text for header in headers]), *rows])
