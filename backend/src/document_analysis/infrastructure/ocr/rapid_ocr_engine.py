from rapidocr import RapidOCR

from src.document_analysis.domain.ocr_layout import OcrFragment, layout_ocr_text

LOG_LEVEL_KEY = "Global.log_level"
LOG_LEVEL = "warning"


def to_fragment(box: list[list[float]], text: str, page_width: int, page_height: int) -> OcrFragment:
    xs = [point[0] for point in box]
    ys = [point[1] for point in box]
    return OcrFragment(
        text=text,
        x_center=(min(xs) + max(xs)) / 2 / page_width,
        y_center=(min(ys) + max(ys)) / 2 / page_height,
        width=max(xs) - min(xs),
        height=max(ys) - min(ys),
    )


class RapidOcrEngine:
    def __init__(self) -> None:
        self.engine = RapidOCR(params={LOG_LEVEL_KEY: LOG_LEVEL})

    def read(self, image_png: bytes) -> str:
        result = self.engine(image_png)
        if result.txts is None:
            return ""
        page_height, page_width = result.img.shape[:2]
        fragments = [to_fragment(box, text, page_width, page_height) for box, text in zip(result.boxes, result.txts, strict=True)]
        return layout_ocr_text(fragments)
