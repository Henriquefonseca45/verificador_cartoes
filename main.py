from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from classifier import ClassifiedCard, classify_card
from config import RuntimeConfig, WRITE_DEBUG_LOG
from extractor import extract_card_data
from exporter import export_debug_json, export_grouped_pdfs, export_review_csv, export_summary_json
from grouper import group_cards
from reader_pdf import iter_all_cards
from rules import normalize_text


def load_client_colors(path: Path) -> Dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {normalize_text(client): normalize_text(color) for client, color in raw.items()}


def ensure_runtime_dirs(cfg: RuntimeConfig) -> None:
    cfg.input_dir.mkdir(parents=True, exist_ok=True)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    cfg.temp_dir.mkdir(parents=True, exist_ok=True)


def run(cfg: RuntimeConfig) -> int:
    ensure_runtime_dirs(cfg)

    if not cfg.clients_colors_file.exists():
        print(f"Arquivo de cores não encontrado: {cfg.clients_colors_file}")
        return 2

    client_colors = load_client_colors(cfg.clients_colors_file)
    all_cards: List[ClassifiedCard] = []
    extracted_debug_rows: List[dict] = []
    skipped_slots = 0

    found_any_pdf = False
    for open_page in iter_all_cards(cfg.input_dir):
        found_any_pdf = True
        extracted = extract_card_data(open_page)
        if extracted.skip_card:
            skipped_slots += 1
            if WRITE_DEBUG_LOG:
                extracted_debug_rows.append({
                    "arquivo": str(open_page.source.pdf_path),
                    "pagina": open_page.source.page_number + 1,
                    "cartao": open_page.source.card_index,
                    **extracted.debug_text,
                })
            continue

        classified = classify_card(open_page.source, extracted, client_colors)
        all_cards.append(classified)
        extracted_debug_rows.append(extracted.debug_text)

    if not found_any_pdf:
        print(f"Nenhum PDF encontrado em: {cfg.input_dir}")
        return 1

    grouped_cards, review_cards = group_cards(all_cards)
    exported_files = export_grouped_pdfs(grouped_cards, cfg.output_dir)
    review_csv = export_review_csv(review_cards, cfg.logs_dir)
    summary_json = export_summary_json(all_cards, exported_files, cfg.logs_dir)

    if WRITE_DEBUG_LOG:
        export_debug_json(all_cards, cfg.logs_dir, extracted_debug_rows[: len(all_cards)])

    print("Processamento concluído.")
    print(f"Cartões válidos analisados: {len(all_cards)}")
    print(f"Slots vazios ignorados: {skipped_slots}")
    print(f"Grupos exportados: {len(exported_files)}")
    print(f"Arquivo de revisão: {review_csv}")
    print(f"Resumo: {summary_json}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verificador de cartões PDF")
    parser.add_argument("--input", type=Path, default=RuntimeConfig().input_dir, help="Pasta com PDFs de entrada")
    parser.add_argument("--output", type=Path, default=RuntimeConfig().output_dir, help="Pasta com PDFs agrupados")
    parser.add_argument("--logs", type=Path, default=RuntimeConfig().logs_dir, help="Pasta de logs")
    parser.add_argument("--colors", type=Path, default=RuntimeConfig().clients_colors_file, help="Arquivo JSON de cliente x cor")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg = RuntimeConfig(
        input_dir=args.input,
        output_dir=args.output,
        logs_dir=args.logs,
        clients_colors_file=args.colors,
    )
    raise SystemExit(run(cfg))
