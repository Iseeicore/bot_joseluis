import sys
from pathlib import Path

import pymupdf

CHARS_PER_TOKEN = 3.5
EMPTY_PAGE_CHARS = 50


def extract(pdf: Path, output_dir: Path) -> dict:
    with pymupdf.open(pdf) as doc:
        pages = [page.get_text() for page in doc]
        images = sum(len(page.get_images()) for page in doc)
    sizes = [len(text) for text in pages]
    (output_dir / f"{pdf.stem}.txt").write_text("\n\n".join(pages), encoding="utf-8")
    return {
        "file": pdf.name,
        "pages": len(pages),
        "chars": sum(sizes),
        "tokens": int(sum(sizes) / CHARS_PER_TOKEN),
        "empty_pages": sum(1 for size in sizes if size < EMPTY_PAGE_CHARS),
        "images": images,
    }


def main(samples_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"{'file':34} {'pages':>5} {'chars':>8} {'tokens':>7} {'empty':>6} {'imgs':>5}")
    for pdf in sorted(samples_dir.glob("*.pdf")):
        r = extract(pdf, output_dir)
        print(f"{r['file']:34} {r['pages']:5d} {r['chars']:8d} {r['tokens']:7d} {r['empty_pages']:6d} {r['images']:5d}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
