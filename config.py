from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"
CLIENTS_COLORS_FILE = BASE_DIR / "clients_colors.json"

# Layout real observado nos cartões de teste: até 6 cartões por página
# em grade 2 x 3. Páginas com menos cartões usam apenas alguns slots.
CARD_REGIONS: List[Tuple[float, float, float, float]] = [
    (0.04, 0.03, 0.48, 0.33),
    (0.52, 0.03, 0.96, 0.33),
    (0.04, 0.35, 0.48, 0.65),
    (0.52, 0.35, 0.96, 0.65),
    (0.04, 0.68, 0.48, 0.98),
    (0.52, 0.68, 0.96, 0.98),
]

# Mantidos apenas para compatibilidade do projeto anterior.
CLIENT_RECT_NORM = (0.17, 0.15, 0.49, 0.25)
PROCESS_TABLE_RECT_NORM = (0.10, 0.68, 0.95, 0.92)
CARD_CLIENT_RECT_NORM = (0.31, 0.08, 0.67, 0.17)
CARD_FIRST_PROCESS_RECT_NORM = (0.02, 0.68, 0.15, 0.82)
PROCESS_COLUMNS = ["D", "P", "CC", "FU2", "DEP", "CP", "CP4", "CP5", "A3", "D3", "F", "A", "CM", "SEE", "DPP", "FP4", "FP5", "FP3", "P6", "MCM", "P2", "E"]
PROCESS_HEADER_HEIGHT_RATIO = 0.25
PROCESS_ANY_TEXT_IS_VALID = True
PROCESS_VALID_TEXT_PATTERN = r".+"

CLIENT_ALIASES: Dict[str, str] = {
    "WEG BETIM": "WEG BETIM",
    "WEG GRAVATAI": "WEG GRAVATAI",
    "WEG BLUMENAU": "WEG BLUMENAU",
    "BLUTRAFOS": "BLUTRAFOS",
}

ENABLE_OCR_FALLBACK = False
OCR_LANGUAGE = "por"
WRITE_DEBUG_LOG = True


@dataclass(frozen=True)
class RuntimeConfig:
    input_dir: Path = INPUT_DIR
    output_dir: Path = OUTPUT_DIR
    logs_dir: Path = LOGS_DIR
    temp_dir: Path = TEMP_DIR
    clients_colors_file: Path = CLIENTS_COLORS_FILE
