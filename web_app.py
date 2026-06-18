from __future__ import annotations

import io
import os
import re
import traceback
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from uuid import uuid4

from flask import Flask, abort, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from config import RuntimeConfig
from main import run


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data")).resolve()
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "200"))
JOB_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


def job_dir(job_id: str) -> Path:
    if not JOB_ID_PATTERN.fullmatch(job_id):
        abort(404)
    return DATA_DIR / "jobs" / job_id


def create_result_zip(root: Path) -> Path:
    zip_path = root / "resultados.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder_name in ("output", "logs"):
            folder = root / folder_name
            for path in sorted(folder.glob("*")):
                if path.is_file():
                    archive.write(path, arcname=f"{folder_name}/{path.name}")
        process_log = root / "processamento.log"
        if process_log.is_file():
            archive.write(process_log, arcname=process_log.name)
    return zip_path


@app.get("/")
def index():
    return render_template("index.html", max_upload_mb=MAX_UPLOAD_MB)


@app.post("/processar")
def process_files():
    uploaded_files = [
        uploaded
        for uploaded in request.files.getlist("pdfs")
        if uploaded.filename
    ]
    invalid_names = [
        uploaded.filename
        for uploaded in uploaded_files
        if Path(uploaded.filename).suffix.lower() != ".pdf"
    ]

    if not uploaded_files:
        return render_template(
            "index.html",
            error="Selecione pelo menos um arquivo PDF.",
            max_upload_mb=MAX_UPLOAD_MB,
        ), 400

    if invalid_names:
        return render_template(
            "index.html",
            error="Apenas arquivos PDF sao permitidos.",
            max_upload_mb=MAX_UPLOAD_MB,
        ), 400

    job_id = uuid4().hex
    root = job_dir(job_id)
    input_dir = root / "input"
    output_dir = root / "output"
    logs_dir = root / "logs"
    temp_dir = root / "temp"
    input_dir.mkdir(parents=True)

    for index, uploaded in enumerate(uploaded_files, start=1):
        filename = secure_filename(uploaded.filename) or f"arquivo_{index}.pdf"
        destination = input_dir / filename
        suffix = 2
        while destination.exists():
            destination = input_dir / f"{Path(filename).stem}_{suffix}.pdf"
            suffix += 1
        uploaded.save(destination)

    cfg = RuntimeConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        logs_dir=logs_dir,
        temp_dir=temp_dir,
        clients_colors_file=BASE_DIR / "clients_colors.json",
    )

    console_output = io.StringIO()
    try:
        with redirect_stdout(console_output):
            exit_code = run(cfg)
    except Exception:
        exit_code = 1
        console_output.write("\n")
        console_output.write(traceback.format_exc())
    (root / "processamento.log").write_text(
        console_output.getvalue(),
        encoding="utf-8",
    )

    if exit_code != 0:
        return render_template(
            "result.html",
            job_id=job_id,
            error="O processamento nao foi concluido. Consulte o log.",
            output_files=[],
            log_files=["processamento.log"],
        ), 422

    create_result_zip(root)
    output_files = sorted(path.name for path in output_dir.glob("*.pdf"))
    log_files = sorted(path.name for path in logs_dir.glob("*") if path.is_file())
    log_files.append("processamento.log")

    return render_template(
        "result.html",
        job_id=job_id,
        output_files=output_files,
        log_files=log_files,
    )


@app.get("/jobs/<job_id>/download")
def download_zip(job_id: str):
    root = job_dir(job_id)
    return send_from_directory(root, "resultados.zip", as_attachment=True)


@app.get("/jobs/<job_id>/<folder>/<path:filename>")
def download_file(job_id: str, folder: str, filename: str):
    root = job_dir(job_id)
    if folder not in {"output", "logs"}:
        abort(404)
    return send_from_directory(root / folder, filename, as_attachment=True)


@app.get("/jobs/<job_id>/processamento.log")
def download_process_log(job_id: str):
    root = job_dir(job_id)
    return send_from_directory(root, "processamento.log", as_attachment=True)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/logo_rvb.png")
def logo():
    return send_from_directory(BASE_DIR, "logo_rvb.png")


@app.errorhandler(413)
def request_too_large(_error):
    return render_template(
        "index.html",
        error=f"O envio ultrapassou o limite de {MAX_UPLOAD_MB} MB.",
        max_upload_mb=MAX_UPLOAD_MB,
    ), 413


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=8080)
