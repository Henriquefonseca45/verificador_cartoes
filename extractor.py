from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

import pymupdf as fitz

from config import CARD_CLIENT_RECT_NORM, CARD_FIRST_PROCESS_RECT_NORM, CLIENT_ALIASES, ENABLE_OCR_FALLBACK, OCR_LANGUAGE, PROCESS_COLUMNS
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


def _collapse_repeated_token(token: str, candidates: List[str] | None = None) -> str:
    raw = str(token or "").strip()
    norm = normalize_text(raw)
    if not norm:
        return raw

    if candidates:
        for candidate in sorted(candidates, key=len, reverse=True):
            candidate_norm = normalize_text(candidate)
            if candidate_norm and norm == candidate_norm * (len(norm) // len(candidate_norm)):
                return candidate

    for size in range(1, (len(norm) // 2) + 1):
        if len(norm) % size:
            continue
        part = norm[:size]
        if part and part * (len(norm) // size) == norm:
            return part

    return raw


def _normalize_repeated_text(text: str) -> str:
    tokens = re.findall(r"[A-Z0-9ÃƒÃ‡Ã‰Ã“Ã€ÃšÃÕÃÂÃÊÃÔÃÄÃËÃÏÃ–ÃÜÇÁÉÍÓÚÀÕÂÊÔÄËÏÖÜ_-]+|[^\s]+", normalize_text(text))
    normalized = [_collapse_repeated_token(token) for token in tokens]
    return " ".join(token for token in normalized if token)


def _line_after_marker(lines: List[str], marker: str) -> str:
    marker_norm = normalize_text(marker)
    for idx, line in enumerate(lines):
        if _collapse_repeated_token(normalize_text(line)) == marker_norm:
            for next_line in lines[idx + 1:]:
                if normalize_text(next_line):
                    return next_line.strip()
    return ""


def _relative_rect(parent: fitz.Rect, norm_rect) -> fitz.Rect:
    return fitz.Rect(
        parent.x0 + parent.width * norm_rect[0],
        parent.y0 + parent.height * norm_rect[1],
        parent.x0 + parent.width * norm_rect[2],
        parent.y0 + parent.height * norm_rect[3],
    )


def _find_known_client(text: str) -> str:
    normalized = _normalize_repeated_text(text)
    aliases = [client for client in CLIENT_ALIASES if client != "__DEFAULT__"]
    for client in sorted(aliases, key=len, reverse=True):
        if normalize_text(client) in normalized:
            return CLIENT_ALIASES.get(client, client)
    return ""


def _clean_client_from_fixed_area(text: str) -> str:
    client = _find_known_client(text)
    if client:
        return client

    cleaned_lines = []
    for line in _clean_lines(text):
        cleaned = _normalize_repeated_text(line)
        if normalize_text(cleaned) == "CLIENTE":
            continue
        cleaned_lines.append(cleaned)
    return " ".join(cleaned_lines).strip()


def _extract_process_tokens(line: str) -> List[str]:
    compact = re.sub(r"[^A-Z0-9-]+", "", normalize_text(line))
    tokens: List[str] = []
    pos = 0
    process_names = sorted(PROCESS_COLUMNS, key=len, reverse=True)

    while pos < len(compact):
        matched = False
        for process in process_names:
            proc = normalize_text(process)
            if compact.startswith(proc, pos):
                end = pos + len(proc)
                while compact.startswith(proc, end):
                    end += len(proc)
                tokens.append(process)
                pos = end
                matched = True
                break
        if not matched:
            pos += 1

    return tokens


def _first_process_from_fixed_area(text: str) -> str:
    tokens = _extract_process_tokens(text)
    return tokens[0] if tokens else ""


def _extract_status_tokens(line: str) -> List[str]:
    compact = re.sub(r"[^A-Z0-9Ãƒ]+", "", normalize_text(line))
    tokens: List[str] = []
    pos = 0

    while pos < len(compact):
        if compact.startswith("SIM", pos):
            end = pos + 3
            while compact.startswith("SIM", end):
                end += 3
            tokens.append("SIM")
            pos = end
            continue
        if compact.startswith("NAO", pos) or compact.startswith("NÃƒO", pos):
            marker = "NAO" if compact.startswith("NAO", pos) else "NÃƒO"
            end = pos + len(marker)
            while compact.startswith(marker, end):
                end += len(marker)
            tokens.append("NAO")
            pos = end
            continue
        pos += 1

    return tokens


def _normalize_repeated_text(text: str) -> str:
    tokens = re.findall(r"[A-Z0-9_-]+|[^\s]+", normalize_text(text))
    normalized = [_collapse_repeated_token(token) for token in tokens]
    return " ".join(token for token in normalized if token)


def _extract_status_tokens(line: str) -> List[str]:
    compact = re.sub(r"[^A-Z0-9]+", "", normalize_text(line).replace("NÃƒO", "NAO"))
    tokens: List[str] = []
    pos = 0

    while pos < len(compact):
        if compact.startswith("SIM", pos):
            end = pos + 3
            while compact.startswith("SIM", end):
                end += 3
            tokens.append("SIM")
            pos = end
            continue
        if compact.startswith("NAO", pos):
            end = pos + 3
            while compact.startswith("NAO", end):
                end += 3
            tokens.append("NAO")
            pos = end
            continue
        pos += 1

    return tokens


def _parse_process_values(lines: List[str]) -> Dict[str, str]:
    process_line = ""
    status_line = ""

    for idx, line in enumerate(lines):
        if _collapse_repeated_token(normalize_text(line)) == "ROTEIRO":
            if idx + 1 < len(lines):
                process_line = lines[idx + 1].strip()
            for candidate in lines[idx + 2: idx + 5]:
                norm = normalize_text(candidate)
                if "SIM" in norm or "NAO" in norm:
                    status_line = candidate.strip()
                    break
            break

    process_tokens = _extract_process_tokens(process_line)
    status_tokens = _extract_status_tokens(status_line)
    values: Dict[str, str] = {}

    if process_tokens and status_tokens and len(process_tokens) == len(status_tokens):
        for proc, status in zip(process_tokens, status_tokens):
            values[proc] = status
        return values

    if process_tokens:
        for proc in process_tokens:
            values[proc] = "SIM"
    return values


def _normalize_marker_line(line: str) -> str:
    return _normalize_repeated_text(line).replace(" ", "")


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
        marker_line = _normalize_marker_line(line)
        if target.replace(" ", "") in marker_line:
            same_line_status = parse_yes_no(marker_line.replace(target.replace(" ", ""), " ", 1))
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
    client_rect = _relative_rect(card_rect, CARD_CLIENT_RECT_NORM)
    first_process_rect = _relative_rect(card_rect, CARD_FIRST_PROCESS_RECT_NORM)
    fixed_client_text = extract_text_in_rect(page, client_rect)
    fixed_process_text = extract_text_in_rect(page, first_process_rect)
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

    raw_client = _clean_client_from_fixed_area(fixed_client_text) or _find_known_client(full_text) or _line_after_marker(lines, "CLIENTE")
    process_values = _parse_process_values(lines)
    first_fixed_process = _first_process_from_fixed_area(fixed_process_text)
    if first_fixed_process:
        process_values = {first_fixed_process: "SIM"}
    process_line = " ".join(process_values.keys())
    has_technical_drawing = _parse_technical_drawing(lines)

    return ExtractedCardData(
        raw_client=raw_client,
        process_values=process_values,
        has_technical_drawing=has_technical_drawing,
        debug_text={
            "card_rect": str(card_rect),
            "client_rect": str(client_rect),
            "first_process_rect": str(first_process_rect),
            "fixed_client_text": fixed_client_text,
            "fixed_process_text": fixed_process_text,
            "raw_client": raw_client,
            "process_line": process_line,
            "process_values": process_values,
            "has_technical_drawing": has_technical_drawing,
            "full_text": full_text,
        },
        skip_card=False,
    )
