from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, Optional

from config import CLIENT_ALIASES, PROCESS_ANY_TEXT_IS_VALID, PROCESS_VALID_TEXT_PATTERN


def normalize_text(value: str) -> str:
    value = str(value or "").strip().upper()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"\s+", " ", value)
    return value


def normalize_client(raw_client: str) -> str:
    normalized = normalize_text(raw_client)
    return CLIENT_ALIASES.get(normalized, normalized)


def is_column_valid(raw_value: str) -> bool:
    text = normalize_text(raw_value)
    if not text:
        return False
    if PROCESS_ANY_TEXT_IS_VALID:
        return True
    return re.search(PROCESS_VALID_TEXT_PATTERN, text) is not None


def first_valid_process(process_values: Dict[str, str], process_order: Iterable[str]) -> Optional[str]:
    for process_name in process_order:
        if is_column_valid(process_values.get(process_name, "")):
            return process_name
    return None


def build_group_key(process_name: str, client: str, color: str) -> str:
    return f"{normalize_text(process_name)}__{normalize_text(client)}__{normalize_text(color)}"


def build_output_filename(process_name: str, client: str, color: str) -> str:
    safe = [normalize_text(process_name), normalize_text(client), normalize_text(color)]
    safe = [re.sub(r"[^A-Z0-9_ -]", "", part).replace(" ", "_") for part in safe]
    return "_".join(safe) + ".pdf"
