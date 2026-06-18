from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import queue
import re
import shutil
import sys
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk


APP_TITLE = "Verificador de Cartões RVB"

DEFAULT_COLORS = {
    "WEG BLUMENAU": "AZUL",
    "WEG BETIM": "VERMELHO",
    "WEG GRAVATAI": "LARANJA",
    "TRAEL MATRIX": "VERDE",
    "TRAEL MATRIZ": "VERDE",
    "TRAEL FILIAL": "VERDE",
    "COMTRAFO 1": "MARROM",
    "COMTRAFO 2": "MARROM",
    "COMTRAFO 3": "MARROM",
    "COMTRAFO 4": "MARROM",
    "HITACHI ENERGY BRASIL LTDA": "AMARELO",
    "PFIFFNER": "CINZA",
    "BLUTRAFOS": "BRANCO",
}
DEFAULT_FALLBACK_COLOR = "BRANCO"


class QueueWriter:
    def __init__(self, put_func):
        self.put_func = put_func
        self.buffer = ""

    def write(self, text):
        if not text:
            return
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.rstrip()
            if line:
                self.put_func(line)

    def flush(self):
        if self.buffer.strip():
            self.put_func(self.buffer.strip())
        self.buffer = ""


class VerificadorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1240x820")
        self.minsize(1080, 720)
        self.configure(bg="#eef2f7")

        if getattr(sys, "frozen", False):
            self.base_dir = Path(sys.executable).resolve().parent
            self.resource_dir = Path(getattr(sys, "_MEIPASS", self.base_dir))
        else:
            self.base_dir = Path(__file__).resolve().parent
            self.resource_dir = self.base_dir

        self.input_dir = self.base_dir / "input"
        self.output_dir = self.base_dir / "output"
        self.logs_dir = self.base_dir / "logs"

        self.main_script = self.resource_dir / "main.py"
        self.clients_file = self.base_dir / "clients_colors.json"
        self.logo_file = self.resource_dir / "logo_rvb.png"

        self.selected_files: list[Path] = []
        self.process_thread: threading.Thread | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.logo_image = None

        self._ensure_dirs()
        self._write_fixed_clients_file()

        self._setup_style()
        self._build_ui()
        self.after(150, self._drain_log_queue)

    def _setup_style(self) -> None:
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.style.configure("App.TFrame", background="#eef2f7")
        self.style.configure("Card.TFrame", background="#ffffff")
        self.style.configure("Header.TFrame", background="#17324d")
        self.style.configure(
            "HeaderTitle.TLabel",
            background="#17324d",
            foreground="#ffffff",
            font=("Segoe UI", 18, "bold"),
        )
        self.style.configure(
            "HeaderSub.TLabel",
            background="#17324d",
            foreground="#d8e6f5",
            font=("Segoe UI", 10),
        )
        self.style.configure(
            "SectionTitle.TLabel",
            background="#ffffff",
            foreground="#18344f",
            font=("Segoe UI", 12, "bold"),
        )
        self.style.configure(
            "Hint.TLabel",
            background="#ffffff",
            foreground="#62748a",
            font=("Segoe UI", 9),
        )
        self.style.configure("CardTitle.TLabelframe", background="#ffffff", foreground="#18344f")
        self.style.configure(
            "CardTitle.TLabelframe.Label",
            background="#ffffff",
            foreground="#18344f",
            font=("Segoe UI", 10, "bold"),
        )
        self.style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 8))
        self.style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(10, 8))
        self.style.configure(
            "SummaryValue.TLabel",
            background="#ffffff",
            foreground="#17324d",
            font=("Segoe UI", 15, "bold"),
        )
        self.style.configure(
            "SummaryLabel.TLabel",
            background="#ffffff",
            foreground="#6b7b8d",
            font=("Segoe UI", 9),
        )

    def _ensure_dirs(self) -> None:
        self.input_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)

    def _write_fixed_clients_file(self) -> None:
        fixed_rules = dict(DEFAULT_COLORS)
        fixed_rules["__DEFAULT__"] = DEFAULT_FALLBACK_COLOR
        with self.clients_file.open("w", encoding="utf-8") as f:
            json.dump(fixed_rules, f, ensure_ascii=False, indent=2)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, style="Header.TFrame", padding=(22, 18))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        logo_label = tk.Label(header, bg="#17324d", borderwidth=0, highlightthickness=0)
        logo_label.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 16))
        self._apply_logo(logo_label)

        title_wrap = ttk.Frame(header, style="Header.TFrame")
        title_wrap.grid(row=0, column=1, rowspan=2, sticky="w")
        ttk.Label(title_wrap, text=APP_TITLE, style="HeaderTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_wrap,
            text="Organize os PDFs por processo, cliente e cor em poucos cliques.",
            style="HeaderSub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        body = ttk.Frame(self, style="App.TFrame", padding=16)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        stats = ttk.Frame(body, style="App.TFrame")
        stats.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        for i in range(4):
            stats.columnconfigure(i, weight=1)

        self.stat_files = self._create_stat_card(stats, 0, "PDFs selecionados", "0")
        self.stat_groups = self._create_stat_card(stats, 1, "Grupos exportados", "0")
        self.stat_valid = self._create_stat_card(stats, 2, "Cartões válidos", "0")
        self.stat_review = self._create_stat_card(stats, 3, "Em revisão", "0")

        content = ttk.Frame(body, style="Card.TFrame", padding=16)
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(5, weight=1)

        self._build_left_panel(content)

    def _apply_logo(self, label: tk.Label) -> None:
        candidates = [
            self.base_dir / "logo_rvb.png",
            self.resource_dir / "logo_rvb.png",
            self.base_dir / "_internal" / "logo_rvb.png",
        ]

        logo_path = None
        for path in candidates:
            if path.exists():
                logo_path = path
                break

        if logo_path is None:
            label.configure(text="RVB", fg="#ffffff", font=("Segoe UI", 18, "bold"))
            return

        try:
            img = Image.open(logo_path)
            resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
            img.thumbnail((220, 80), resample)
            self.logo_image = ImageTk.PhotoImage(img)
            label.configure(image=self.logo_image, text="")
        except Exception:
            label.configure(text="RVB", fg="#ffffff", font=("Segoe UI", 18, "bold"))

    def _create_stat_card(self, parent: ttk.Frame, column: int, label: str, value: str) -> ttk.Label:
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
        card.columnconfigure(0, weight=1)

        value_lbl = ttk.Label(card, text=value, style="SummaryValue.TLabel")
        value_lbl.grid(row=0, column=0, sticky="w")
        ttk.Label(card, text=label, style="SummaryLabel.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        return value_lbl

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="Card.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Arquivos selecionados", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Adicione um ou mais PDFs para processar.", style="Hint.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))

        actions = ttk.Frame(header, style="Card.TFrame")
        actions.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Button(actions, text="Adicionar PDFs", style="Primary.TButton", command=self._select_files).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="Remover selecionado", style="Secondary.TButton", command=self._remove_selected_file).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="Limpar lista", style="Secondary.TButton", command=self._clear_files).grid(row=0, column=2)

        list_frame = ttk.Frame(parent, style="Card.TFrame")
        list_frame.grid(row=1, column=0, sticky="nsew", pady=(12, 14))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.files_list = tk.Listbox(
            list_frame,
            height=10,
            font=("Segoe UI", 10),
            relief="flat",
            bd=0,
            activestyle="none",
            selectbackground="#d8e7f7",
            selectforeground="#17324d",
        )
        self.files_list.grid(row=0, column=0, sticky="nsew")

        files_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.files_list.yview)
        files_scroll.grid(row=0, column=1, sticky="ns")
        self.files_list.configure(yscrollcommand=files_scroll.set)

        process_box = ttk.LabelFrame(parent, text="Processamento", style="CardTitle.TLabelframe", padding=14)
        process_box.grid(row=2, column=0, sticky="ew")
        process_box.columnconfigure(1, weight=1)

        ttk.Label(process_box, text="Entrada:").grid(row=0, column=0, sticky="w")
        self.input_var = tk.StringVar(value=str(self.input_dir))
        ttk.Entry(process_box, textvariable=self.input_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(process_box, text="Abrir", style="Secondary.TButton", command=lambda: self._open_folder(self.input_dir)).grid(row=0, column=2)

        ttk.Label(process_box, text="Saída:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.output_var = tk.StringVar(value=str(self.output_dir))
        ttk.Entry(process_box, textvariable=self.output_var, state="readonly").grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        ttk.Button(process_box, text="Abrir", style="Secondary.TButton", command=lambda: self._open_folder(self.output_dir)).grid(row=1, column=2, pady=(8, 0))

        buttons = ttk.Frame(process_box, style="Card.TFrame")
        buttons.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        for i in range(3):
            buttons.columnconfigure(i, weight=1)

        self.process_button = ttk.Button(buttons, text="Processar PDFs", style="Primary.TButton", command=self._start_processing)
        self.process_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="Abrir saída", style="Secondary.TButton", command=lambda: self._open_folder(self.output_dir)).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(buttons, text="Limpar saída", style="Secondary.TButton", command=self._clear_output).grid(row=0, column=2, sticky="ew", padx=(6, 0))

        progress_wrap = ttk.Frame(parent, style="Card.TFrame")
        progress_wrap.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        progress_wrap.columnconfigure(0, weight=1)

        status_row = ttk.Frame(progress_wrap, style="Card.TFrame")
        status_row.grid(row=0, column=0, sticky="ew")
        status_row.columnconfigure(0, weight=1)

        ttk.Label(status_row, text="Status", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.status_var = tk.StringVar(value="Aguardando arquivos para processar.")
        ttk.Label(status_row, textvariable=self.status_var, style="Hint.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.progress = ttk.Progressbar(progress_wrap, mode="indeterminate")
        self.progress.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        summary = ttk.LabelFrame(parent, text="Regras fixas de cor", style="CardTitle.TLabelframe", padding=10)
        summary.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        summary.columnconfigure(0, weight=1)
        summary.columnconfigure(1, weight=1)

        rules_lines = [
            ("WEG BLUMENAU", "AZUL"),
            ("WEG BETIM", "VERMELHO"),
            ("WEG GRAVATAI", "LARANJA"),
            ("TRAEL MATRIX", "VERDE"),
            ("TRAEL FILIAL", "VERDE"),
            ("COMTRAFO 1", "MARROM"),
            ("COMTRAFO 2", "MARROM"),
            ("COMTRAFO 3", "MARROM"),
            ("COMTRAFO 4", "MARROM"),
            ("HITACHI ENERGY BRASIL LTDA", "AMARELO"),
            ("PFIFFNER", "CINZA"),
            ("QUALQUER OUTRO CLIENTE", "BRANCO"),
        ]

        half = (len(rules_lines) + 1) // 2
        left_rules = rules_lines[:half]
        right_rules = rules_lines[half:]

        left_text = "\n".join([f"{client} = {color}" for client, color in left_rules])
        right_text = "\n".join([f"{client} = {color}" for client, color in right_rules])

        ttk.Label(
            summary,
            text=left_text,
            justify="left",
            background="#ffffff",
            foreground="#17324d",
            font=("Segoe UI", 9),
        ).grid(row=0, column=0, sticky="nw", padx=(0, 20))

        ttk.Label(
            summary,
            text=right_text,
            justify="left",
            background="#ffffff",
            foreground="#17324d",
            font=("Segoe UI", 9),
        ).grid(row=0, column=1, sticky="nw")

        log_frame = ttk.LabelFrame(parent, text="Log de execução", style="CardTitle.TLabelframe", padding=12)
        log_frame.grid(row=5, column=0, sticky="nsew", pady=(14, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            font=("Consolas", 10),
            relief="flat",
            bd=0,
            bg="#f7f9fc",
            fg="#1c2c3a",
            height=16,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set, state="disabled")

    def _select_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Selecione os PDFs",
            filetypes=[("Arquivos PDF", "*.pdf")],
        )
        if not paths:
            return

        added = 0
        for raw in paths:
            p = Path(raw)
            if p not in self.selected_files:
                self.selected_files.append(p)
                added += 1

        self._refresh_file_list()
        self._update_file_counter()
        self._log(f"{added} arquivo(s) adicionado(s) à lista.")
        self.status_var.set("Arquivos prontos para processamento.")

    def _remove_selected_file(self) -> None:
        selection = self.files_list.curselection()
        if not selection:
            return
        index = selection[0]
        removed = self.selected_files.pop(index)
        self._refresh_file_list()
        self._update_file_counter()
        self._log(f"Arquivo removido: {removed.name}")

    def _clear_files(self) -> None:
        self.selected_files = []
        self._refresh_file_list()
        self._update_file_counter()
        self._log("Lista de arquivos limpa.")
        self.status_var.set("Aguardando arquivos para processar.")

    def _refresh_file_list(self) -> None:
        self.files_list.delete(0, tk.END)
        for p in self.selected_files:
            display = f"{p.name}   —   {p.parent}"
            self.files_list.insert(tk.END, display)

    def _update_file_counter(self) -> None:
        self.stat_files.configure(text=str(len(self.selected_files)))

    def _start_processing(self) -> None:
        if self.process_thread and self.process_thread.is_alive():
            messagebox.showinfo("Processando", "Já existe um processamento em andamento.")
            return

        if not self.selected_files:
            messagebox.showwarning("Atenção", "Selecione ao menos um PDF.")
            return

        if not self.main_script.exists():
            messagebox.showerror("Erro", f"Não encontrei o arquivo main.py em:\n{self.main_script}")
            return

        self._write_fixed_clients_file()
        self._prepare_input_folder()
        self.process_button.configure(state="disabled")
        self.progress.start(10)
        self.status_var.set("Processando PDFs...")
        self._log("Iniciando processamento...")

        self.process_thread = threading.Thread(target=self._run_processing, daemon=True)
        self.process_thread.start()

    def _prepare_input_folder(self) -> None:
        for existing in self.input_dir.glob("*.pdf"):
            try:
                existing.unlink()
            except Exception:
                pass

        for src in self.selected_files:
            target = self.input_dir / src.name
            shutil.copy2(src, target)

        self._log(f"{len(self.selected_files)} PDF(s) copiado(s) para a pasta input.")

    def _run_processing(self) -> None:
        writer = QueueWriter(self.log_queue.put)

        try:
            os.chdir(self.base_dir)

            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                spec = importlib.util.spec_from_file_location("processor_main", str(self.main_script))
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"Não foi possível carregar {self.main_script}")

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, "run") and callable(module.run):
                    from config import RuntimeConfig

                    cfg = RuntimeConfig(
                        input_dir=self.input_dir,
                        output_dir=self.output_dir,
                        logs_dir=self.logs_dir,
                        clients_colors_file=self.clients_file,
                    )
                    result = module.run(cfg)
                    if result not in (0, None):
                        raise RuntimeError(f"Processamento retornou código {result}")
                elif hasattr(module, "main") and callable(module.main):
                    module.main()
                else:
                    raise RuntimeError("O arquivo main.py não possui função run() nem main().")

            writer.flush()
            self.log_queue.put("Processamento concluído com sucesso.")

        except Exception as exc:
            self.log_queue.put(f"Erro ao executar processamento: {exc}")
            self.log_queue.put(traceback.format_exc())
        finally:
            self.after(0, self._finish_processing)

    def _finish_processing(self) -> None:
        self.process_button.configure(state="normal")
        self.progress.stop()
        self._refresh_summary()
        self.status_var.set("Processamento finalizado.")

    def _summary_value(self, data: dict, *keys: str) -> int:
        for key in keys:
            if key in data:
                try:
                    return int(data.get(key, 0))
                except Exception:
                    pass
        return 0

    def _parse_review_count_from_csv(self) -> int:
        review_file = self.logs_dir / "cards_review.csv"
        if not review_file.exists():
            return 0
        try:
            with review_file.open("r", encoding="utf-8", errors="replace") as f:
                lines = [line for line in f.read().splitlines() if line.strip()]
            return max(0, len(lines) - 1)
        except Exception:
            return 0

    def _parse_summary_from_log(self) -> tuple[int, int, int]:
        content = self.log_text.get("1.0", tk.END)

        valid = 0
        empty = 0
        groups = 0

        match_valid = re.search(r"Cartões válidos analisados:\s*(\d+)", content)
        match_empty = re.search(r"Slots vazios ignorados:\s*(\d+)", content)
        match_groups = re.search(r"Grupos exportados:\s*(\d+)", content)

        if match_valid:
            valid = int(match_valid.group(1))
        if match_empty:
            empty = int(match_empty.group(1))
        if match_groups:
            groups = int(match_groups.group(1))

        return valid, empty, groups

    def _refresh_summary(self) -> None:
        summary_file = self.logs_dir / "summary.json"
        data = {}

        if summary_file.exists():
            try:
                with summary_file.open("r", encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        valid_cards = self._summary_value(data, "valid_cards", "cartoes_validos", "cartoes_validos_analisados")
        empty_slots = self._summary_value(data, "empty_slots", "slots_vazios", "slots_vazios_ignorados")
        exported_groups = self._summary_value(data, "exported_groups", "grupos_exportados")
        review_cards = self._summary_value(data, "review_cards", "cartoes_revisao", "cartoes_em_revisao")

        if valid_cards == 0 and exported_groups == 0:
            log_valid, log_empty, log_groups = self._parse_summary_from_log()
            if log_valid:
                valid_cards = log_valid
            if log_empty:
                empty_slots = log_empty
            if log_groups:
                exported_groups = log_groups

        if review_cards == 0:
            review_cards = self._parse_review_count_from_csv()

        self.stat_valid.configure(text=str(valid_cards))
        self.stat_groups.configure(text=str(exported_groups))
        self.stat_review.configure(text=str(review_cards))

    def _drain_log_queue(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._log(line)
        self.after(150, self._drain_log_queue)

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _clear_output(self) -> None:
        if not self.output_dir.exists():
            return

        if not messagebox.askyesno("Confirmar", "Deseja apagar os arquivos atuais da pasta de saída?"):
            return

        removed = 0
        for item in self.output_dir.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                    removed += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    removed += 1
            except Exception:
                pass

        self._log(f"Saída limpa. {removed} item(ns) removido(s).")

    def _open_folder(self, path: Path) -> None:
        try:
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível abrir a pasta.\n\n{exc}")


if __name__ == "__main__":
    app = VerificadorApp()
    app.mainloop()