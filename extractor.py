from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pymupdf as fitz

from config import ENABLE_OCR_FALLBACK, OCR_LANGUAGE
from reader_pdf import OpenPage
from rules import normalize_text


@dataclass
class ExtractedCardData:
    raw_client: str
    process_values: Dict[str, str]
    has_technical_drawing: bool
    debug_text: Dict[str, str]
    skip_card: bool = False


def extract_text_in_rect(page: fitz.Page, rect: fitz.Rect) -> str:
    text = page.get_text("text", clip=rect, sort=True)
    if normalize_text(text):
        return text.strip()

    if ENABLE_OCR_FALLBACK:
        tp = page.get_textpage_ocr(flags=0, language=OCR_LANGUAGE, dpi=300, full=False, clip=rect)
        return tp.extractText().strip()

    return ""


def _clean_lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if normalize_text(line)]


def _line_after_marker(lines: List[str], marker: str) -> str:
    marker_norm = normalize_text(marker)
    for idx, line in enumerate(lines):
        if normalize_text(line) == marker_norm:
            for next_line in lines[idx + 1:]:
                if normalize_text(next_line):
                    return next_line.strip()
    return ""


def _parse_process_values(lines: List[str]) -> Dict[str, str]:
    process_line = ""
    status_line = ""

    for idx, line in enumerate(lines):
        if normalize_text(line) == "ROTEIRO":
            if idx + 1 < len(lines):
                process_line = lines[idx + 1].strip()
            for candidate in lines[idx + 2: idx + 5]:
                norm = normalize_text(candidate)
                if "SIM" in norm or "NAO" in norm:
                    status_line = candidate.strip()
                    break
            break

    process_tokens = process_line.split()
    status_tokens = status_line.split()
    values: Dict[str, str] = {}

    if process_tokens and status_tokens and len(process_tokens) == len(status_tokens):
        for proc, status in zip(process_tokens, status_tokens):
            values[proc] = status
        return values

    if process_tokens:
        for proc in process_tokens:
            values[proc] = "SIM"
    return values


def _parse_technical_drawing(lines: List[str]) -> bool:
    target = "DESENHO TECNICO"

    def parse_yes_no(text: str) -> bool | None:
        tokens = normalize_text(text).replace(":", " ").replace("-", " ").split()
        for token in tokens:
            if token in {"SIM", "S"}:
                return True
            if token in {"NAO", "N"}:
                return False
        return None

    for idx, line in enumerate(lines):
        norm_line = normalize_text(line)
        if target in norm_line:
            same_line_status = parse_yes_no(norm_line.replace(target, " ", 1))
            if same_line_status is not None:
                return same_line_status
            for candidate in lines[idx + 1: idx + 4]:
                candidate_status = parse_yes_no(candidate)
                if candidate_status is not None:
                    return candidate_status
    return False


def extract_card_data(open_page: OpenPage) -> ExtractedCardData:
    page = open_page.page
    card_rect = open_page.source.card_rect
    full_text = extract_text_in_rect(page, card_rect)
    lines = _clean_lines(full_text)
    normalized_full = normalize_text(full_text)

    looks_like_card = "CLIENTE" in normalized_full and "ROTEIRO" in normalized_full
    if not looks_like_card:
        return ExtractedCardData(
            raw_client="",
            process_values={},
            has_technical_drawing=False,
            debug_text={
                "full_text": full_text,
                "card_rect": str(card_rect),
                "skip_reason": "REGIAO_SEM_CARTAO",
            },
            skip_card=True,
        )

    raw_client = _line_after_marker(lines, "CLIENTE")
    process_values = _parse_process_values(lines)
    process_line = " ".join(process_values.keys())
    has_technical_drawing = _parse_technical_drawing(lines)

    return ExtractedCardData(
        raw_client=raw_client,
        process_values=process_values,
        has_technical_drawing=has_technical_drawing,
        debug_text={
            "card_rect": str(card_rect),
            "raw_client": raw_client,
            "process_line": process_line,
            "process_values": process_values,
            "has_technical_drawing": has_technical_drawing,
            "full_text": full_text,
        },
        skip_card=False,
    )
