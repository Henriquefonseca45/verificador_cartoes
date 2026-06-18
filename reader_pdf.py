from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List

import fitz

from config import CARD_REGIONS


@dataclass
class CardSource:
    pdf_path: Path
    page_number: int
    card_index: int
    page_rect: fitz.Rect
    card_rect: fitz.Rect
    detail_page_number: int | None = None


@dataclass
class OpenPage:
    document: fitz.Document
    page: fitz.Page
    source: CardSource


def list_input_pdfs(input_dir: Path) -> List[Path]:
    return sorted(p for p in input_dir.glob("*.pdf") if p.is_file())


def normalized_rect_to_page(page_rect: fitz.Rect, norm_rect) -> fitz.Rect:
    x0 = page_rect.x0 + page_rect.width * norm_rect[0]
    y0 = page_rect.y0 + page_rect.height * norm_rect[1]
    x1 = page_rect.x0 + page_rect.width * norm_rect[2]
    y1 = page_rect.y0 + page_rect.height * norm_rect[3]
    return fitz.Rect(x0, y0, x1, y1)


def _page_looks_like_cards(page: fitz.Page) -> bool:
    text = page.get_text("text")
    normalized = " ".join(text.upper().split())
    return "CLIENTE" in normalized and "ROTEIRO" in normalized


def iter_cards(pdf_path: Path) -> Iterator[OpenPage]:
    document = fitz.open(pdf_path)
    page_index = 0

    while page_index < document.page_count:
        page = document.load_page(page_index)
        if not _page_looks_like_cards(page):
            page_index += 1
            continue

        detail_page_number = None
        next_index = page_index + 1
        if next_index < document.page_count:
            next_page = document.load_page(next_index)
            if not _page_looks_like_cards(next_page):
                detail_page_number = next_index

        page_rect = page.rect
        for card_index, card_region_norm in enumerate(CARD_REGIONS, start=1):
            card_rect = normalized_rect_to_page(page_rect, card_region_norm)
            source = CardSource(
                pdf_path=pdf_path,
                page_number=page_index,
                card_index=card_index,
                page_rect=page_rect,
                card_rect=card_rect,
                detail_page_number=detail_page_number,
            )
            yield OpenPage(document=document, page=page, source=source)

        page_index += 2 if detail_page_number is not None else 1


def iter_all_cards(input_dir: Path) -> Iterator[OpenPage]:
    for pdf_path in list_input_pdfs(input_dir):
        yield from iter_cards(pdf_path)
