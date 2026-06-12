@echo off
setlocal

cd /d "%~dp0"

echo =========================================
echo   GERANDO O .EXE DO VERIFICADOR RVB
echo =========================================
echo.

pyinstaller --noconfirm --clean --name "VerificadorCartoesRVB_FINAL" --windowed --icon "logo_rvb.ico" --add-data "clients_colors.json;." --add-data "logo_rvb.png;." --add-data "main.py;." --add-data "config.py;." --add-data "rules.py;." --add-data "reader_pdf.py;." --add-data "extractor.py;." --add-data "classifier.py;." --add-data "grouper.py;." --add-data "exporter.py;." --hidden-import "pymupdf" --hidden-import "fitz" --collect-all "pymupdf" desktop_app.py

echo.
echo =========================================
echo   FINALIZADO
echo   O .exe ficara em: dist\VerificadorCartoesRVB_FINAL
echo =========================================
pause