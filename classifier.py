from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import PROCESS_COLUMNS
from extractor import ExtractedCardData
from reader_pdf import CardSource
from rules import build_group_key, normalize_client, normalize_text


@dataclass
class ClassifiedCard:
    source: CardSource
    raw_client: str
    client: str
    color: Optional[str]
    process_values: Dict[str, str]
    first_process: Optional[str]
    has_technical_drawing: bool
    status: str
    issues: List[str] = field(default_factory=list)
    group_key: Optional[str] = None


VALID_STATUS = {"SIM", "S"}
INVALID_STATUS = {"NAO", "NÃO", "N"}


def _first_process_from_dynamic_values(process_values: Dict[str, str]) -> Optional[str]:
    for process_name, raw_status in process_values.items():
        status = str(raw_status or "").strip().upper()
        if status in VALID_STATUS:
            return process_name
        if status in INVALID_STATUS:
            continue
        if status:
            return process_name
    return None


def _group_hint_from_filename(
    source: CardSource,
    client_colors: Dict[str, str],
) -> tuple[str, str, str] | None:
    parts = source.pdf_path.stem.split("_")
    if len(parts) < 3:
        return None

    process = normalize_text(parts[0])
    known_processes = {normalize_text(p) for p in PROCESS_COLUMNS}
    if process not in known_processes:
        return None

    client = normalize_client(" ".join(parts[1:-1]))
    color = normalize_text(parts[-1])
    known_colors = {normalize_text(v) for v in client_colors.values()} | {"BRANCO"}
    if not client or color not in known_colors:
        return None

    return process, client, color


def classify_card(
    source: CardSource,
    extracted: ExtractedCardData,
    client_colors: Dict[str, str],
) -> ClassifiedCard:
    issues: List[str] = []

    client = normalize_client(extracted.raw_client)
    first_process_name = _first_process_from_dynamic_values(extracted.process_values)
    filename_hint = _group_hint_from_filename(source, client_colors)

    default_color = str(client_colors.get("__DEFAULT__", "BRANCO") or "BRANCO").strip().upper()

    if client:
        color = str(client_colors.get(client, default_color) or default_color).strip().upper()
    else:
        color = None

    if filename_hint is not None:
        first_process_name, client, color = filename_hint

    if not client:
        issues.append("CLIENTE_NAO_IDENTIFICADO")

    if not first_process_name:
        issues.append("PROCESSO_NAO_IDENTIFICADO")

    if issues:
        status = "REVISAR"
        group_key = None
    else:
        status = "OK"
        group_key = build_group_key(first_process_name, client, color)

    return ClassifiedCard(
        source=source,
        raw_client=extracted.raw_client,
        client=client,
        color=color,
        process_values=extracted.process_values,
        first_process=first_process_name,
        has_technical_drawing=extracted.has_technical_drawing,
        status=status,
        issues=issues,
        group_key=group_key,
    )
