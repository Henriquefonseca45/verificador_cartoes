from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import fitz
import numpy as np

from classifier import ClassifiedCard
from config import CARD_REGIONS
from rules import build_output_filename


A4_WIDTH = 595.0
A4_HEIGHT = 842.0
DETAIL_SLOT_PADDING = 8.0


def _ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def _slot_rect(slot_index: int) -> fitz.Rect:
    norm = CARD_REGIONS[slot_index - 1]
    return fitz.Rect(
        A4_WIDTH * norm[0],
        A4_HEIGHT * norm[1],
        A4_WIDTH * norm[2],
        A4_HEIGHT * norm[3],
    )


def _padded_slot_rect(slot_index: int, pad: float = DETAIL_SLOT_PADDING) -> fitz.Rect:
    rect = _slot_rect(slot_index)
    return fitz.Rect(rect.x0 + pad, rect.y0 + pad, rect.x1 - pad, rect.y1 - pad)




def _back_slot_index(front_slot_index: int) -> int:
    # Verso espelhado horizontalmente para impressão frente/verso
    # em A4 retrato com virada na borda longa:
    # 1<->2, 3<->4, 5<->6
    mapping = {1: 2, 2: 1, 3: 4, 4: 3, 5: 6, 6: 5}
    return mapping.get(front_slot_index, front_slot_index)
def _fit_rect_preserve_aspect(target: fitz.Rect, source: fitz.Rect) -> fitz.Rect:
    tw = max(1.0, target.width)
    th = max(1.0, target.height)
    sw = max(1.0, source.width)
    sh = max(1.0, source.height)

    scale = min(tw / sw, th / sh)
    w = sw * scale
    h = sh * scale
    x0 = target.x0 + (tw - w) / 2.0
    y0 = target.y0 + (th - h) / 2.0
    return fitz.Rect(x0, y0, x0 + w, y0 + h)


def _expand_rect(rect: fitz.Rect, page_rect: fitz.Rect, margin_x: float = 0.08, margin_y: float = 0.08) -> fitz.Rect:
    dx = max(8.0, rect.width * margin_x)
    dy = max(8.0, rect.height * margin_y)
    expanded = fitz.Rect(rect.x0 - dx, rect.y0 - dy, rect.x1 + dx, rect.y1 + dy)
    return expanded & page_rect


def _build_detail_crop_map(all_grouped_cards: Dict[str, List[ClassifiedCard]]) -> Dict[Tuple[str, int, int], fitz.Rect | None]:
    by_front_page: Dict[Tuple[str, int], List[ClassifiedCard]] = {}
    for cards in all_grouped_cards.values():
        for card in cards:
            key = (str(card.source.pdf_path), card.source.page_number)
            by_front_page.setdefault(key, []).append(card)

    crop_map: Dict[Tuple[str, int, int], fitz.Rect | None] = {}
    doc_cache: Dict[str, fitz.Document] = {}

    try:
        for (pdf_path, front_page_number), page_cards in by_front_page.items():
            detail_page_number = page_cards[0].source.detail_page_number
            if detail_page_number is None:
                for card in page_cards:
                    crop_map[(pdf_path, front_page_number, card.source.card_index)] = None
                continue

            doc = doc_cache.get(pdf_path)
            if doc is None:
                doc = fitz.open(pdf_path)
                doc_cache[pdf_path] = doc

            detail_page = doc.load_page(detail_page_number)
            detail_boxes = _detect_detail_boxes(detail_page)
            sim_cards = sorted([c for c in page_cards if c.has_technical_drawing], key=lambda c: c.source.card_index)
            sim_keys = [(pdf_path, front_page_number, c.source.card_index) for c in sim_cards]

            for key in [(pdf_path, front_page_number, c.source.card_index) for c in page_cards]:
                crop_map[key] = None

            if not sim_cards:
                continue

            if len(detail_boxes) >= len(sim_cards):
                for key, box in zip(sim_keys, detail_boxes[: len(sim_cards)]):
                    crop_map[key] = _expand_rect(box, detail_page.rect)
            elif detail_boxes:
                # Quando a página de detalhe não traz caixas suficientes, tenta usar as maiores.
                # Ainda é melhor do que recortar pela área do cartão de frente.
                detail_boxes = sorted(detail_boxes, key=lambda r: r.get_area(), reverse=True)
                for key, box in zip(sim_keys, detail_boxes):
                    crop_map[key] = _expand_rect(box, detail_page.rect)
            else:
                # Último fallback: usa a página de detalhe inteira, preservando o desenho completo.
                for key in sim_keys:
                    crop_map[key] = detail_page.rect
    finally:
        for doc in doc_cache.values():
            doc.close()

    return crop_map


def _dilate(mask: np.ndarray, radius: int = 3) -> np.ndarray:
    if radius <= 0:
        return mask
    out = mask.copy()
    h, w = mask.shape
    for dy in range(-radius, radius + 1):
        ys_src = slice(max(0, -dy), min(h, h - dy))
        ys_dst = slice(max(0, dy), min(h, h + dy))
        for dx in range(-radius, radius + 1):
            xs_src = slice(max(0, -dx), min(w, w - dx))
            xs_dst = slice(max(0, dx), min(w, w + dx))
            out[ys_dst, xs_dst] |= mask[ys_src, xs_src]
    return out


def _connected_components(mask: np.ndarray) -> List[Tuple[int, int, int, int, int]]:
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: List[Tuple[int, int, int, int, int]] = []

    for y in range(h):
        xs = np.flatnonzero(mask[y] & ~visited[y])
        for x in xs:
            x = int(x)
            stack = [(y, x)]
            visited[y, x] = True
            min_x = max_x = x
            min_y = max_y = y
            area = 0

            while stack:
                cy, cx = stack.pop()
                area += 1
                if cx < min_x:
                    min_x = cx
                if cx > max_x:
                    max_x = cx
                if cy < min_y:
                    min_y = cy
                if cy > max_y:
                    max_y = cy

                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((ny, nx))

            components.append((min_x, min_y, max_x, max_y, area))

    return components


def _merge_nearby_boxes(boxes: List[fitz.Rect], pad: float = 18.0) -> List[fitz.Rect]:
    changed = True
    items = boxes[:]
    while changed:
        changed = False
        merged: List[fitz.Rect] = []
        while items:
            current = items.pop(0)
            i = 0
            while i < len(items):
                other = items[i]
                expand = fitz.Rect(current.x0 - pad, current.y0 - pad, current.x1 + pad, current.y1 + pad)
                if expand.intersects(other):
                    current = current | other
                    items.pop(i)
                    changed = True
                else:
                    i += 1
            merged.append(current)
        items = merged
    return items


def _detect_detail_boxes(page: fitz.Page) -> List[fitz.Rect]:
    # Rasteriza a página e detecta blocos grandes de desenho. A dilatação conecta
    # linhas, cotas e textos próximos para evitar recortes "apertados".
    pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
    channels = max(1, pix.n)
    arr = np.frombuffer(pix.samples, dtype=np.uint8)
    if arr.size == 0:
        return []
    try:
        arr = arr.reshape(pix.height, pix.width, channels)
    except ValueError:
        return []
    if channels >= 3:
        gray = arr[:, :, :3].mean(axis=2).astype(np.uint8)
    else:
        gray = arr[:, :, 0]

    ink = gray < 245
    if not np.any(ink):
        return []

    mask = _dilate(ink, radius=3)
    components = _connected_components(mask)

    if not components:
        return []

    sx = page.rect.width / gray.shape[1]
    sy = page.rect.height / gray.shape[0]
    boxes: List[fitz.Rect] = []

    for x0, y0, x1, y1, area in components:
        width = x1 - x0 + 1
        height = y1 - y0 + 1
        if area < 600:
            continue
        if width < 45 or height < 30:
            continue
        # Ignora linhas horizontais/verticais enormes que costumam ser ruído.
        if width > gray.shape[1] * 0.95 or height > gray.shape[0] * 0.95:
            continue
        rect = fitz.Rect(x0 * sx, y0 * sy, (x1 + 1) * sx, (y1 + 1) * sy)
        boxes.append(rect)

    boxes = _merge_nearby_boxes(boxes, pad=22.0)
    boxes = [_expand_rect(b, page.rect, margin_x=0.06, margin_y=0.10) for b in boxes if b.get_area() > 2500]
    boxes.sort(key=lambda r: (round(r.y0, 1), round(r.x0, 1)))
    return boxes


def export_grouped_pdfs(grouped_cards: Dict[str, List[ClassifiedCard]], output_dir: Path) -> List[Path]:
    _ensure_dirs(output_dir)
    exported_files: List[Path] = []
    docs_cache: Dict[str, fitz.Document] = {}
    detail_crop_map = _build_detail_crop_map(grouped_cards)

    try:
        for cards in grouped_cards.values():
            if not cards:
                continue

            ordered_cards = sorted(cards, key=lambda c: (c.client, c.first_process or "", str(c.source.pdf_path), c.source.page_number, c.source.card_index))
            first = ordered_cards[0]
            output_name = build_output_filename(first.first_process or "SEM_PROCESSO", first.client, first.color or "SEM_COR")
            output_path = output_dir / output_name

            out_doc = fitz.open()
            for batch_start in range(0, len(ordered_cards), 6):
                batch = ordered_cards[batch_start: batch_start + 6]
                front_page = out_doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
                for slot_idx, card in enumerate(batch, start=1):
                    src_path = str(card.source.pdf_path)
                    src_doc = docs_cache.get(src_path)
                    if src_doc is None:
                        src_doc = fitz.open(src_path)
                        docs_cache[src_path] = src_doc
                    front_page.show_pdf_page(_slot_rect(slot_idx), src_doc, card.source.page_number, clip=card.source.card_rect)

                # Sempre cria a página de verso logo após a frente.
                # Quando não houver desenho técnico em nenhum cartão do lote,
                # essa página fica em branco para manter o pareamento frente/verso.
                back_page = out_doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
                for slot_idx, card in enumerate(batch, start=1):
                    if not card.has_technical_drawing or card.source.detail_page_number is None:
                        continue
                    src_path = str(card.source.pdf_path)
                    src_doc = docs_cache.get(src_path)
                    if src_doc is None:
                        src_doc = fitz.open(src_path)
                        docs_cache[src_path] = src_doc
                    crop_key = (src_path, card.source.page_number, card.source.card_index)
                    crop_rect = detail_crop_map.get(crop_key)
                    if crop_rect is None:
                        continue
                    back_slot = _back_slot_index(slot_idx)
                    target = _fit_rect_preserve_aspect(_padded_slot_rect(back_slot), crop_rect)
                    back_page.show_pdf_page(target, src_doc, card.source.detail_page_number, clip=crop_rect)

            out_doc.save(output_path)
            out_doc.close()
            exported_files.append(output_path)
    finally:
        for doc in docs_cache.values():
            doc.close()

    return exported_files


def export_review_csv(review_cards: Iterable[ClassifiedCard], logs_dir: Path) -> Path:
    _ensure_dirs(logs_dir)
    csv_path = logs_dir / "cards_review.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp, delimiter=';')
        writer.writerow([
            "arquivo",
            "pagina",
            "cartao",
            "cliente_bruto",
            "cliente_normalizado",
            "primeiro_processo",
            "cor",
            "desenho_tecnico",
            "status",
            "issues",
        ])
        for card in review_cards:
            writer.writerow([
                str(card.source.pdf_path),
                card.source.page_number + 1,
                card.source.card_index,
                card.raw_client,
                card.client,
                card.first_process or "",
                card.color or "",
                "SIM" if card.has_technical_drawing else "NAO",
                card.status,
                "|".join(card.issues),
            ])

    return csv_path


def export_summary_json(all_cards: List[ClassifiedCard], exported_files: List[Path], logs_dir: Path) -> Path:
    _ensure_dirs(logs_dir)
    summary_path = logs_dir / "summary.json"
    payload = {
        "total_cards": len(all_cards),
        "ok_cards": sum(1 for c in all_cards if c.status == "OK"),
        "review_cards": sum(1 for c in all_cards if c.status != "OK"),
        "cards_with_back_drawing": sum(1 for c in all_cards if c.has_technical_drawing),
        "exported_files": [str(p) for p in exported_files],
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path


def export_debug_json(all_cards: List[ClassifiedCard], logs_dir: Path, extracted_debug_rows: List[dict]) -> Path:
    _ensure_dirs(logs_dir)
    debug_path = logs_dir / "debug_cards.json"
    payload = []
    for card, debug in zip(all_cards, extracted_debug_rows):
        payload.append({
            "arquivo": str(card.source.pdf_path),
            "pagina": card.source.page_number + 1,
            "cartao": card.source.card_index,
            "cliente_bruto": card.raw_client,
            "cliente_normalizado": card.client,
            "primeiro_processo": card.first_process,
            "cor": card.color,
            "desenho_tecnico": card.has_technical_drawing,
            "status": card.status,
            "issues": card.issues,
            "debug": debug,
        })
    debug_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return debug_path
