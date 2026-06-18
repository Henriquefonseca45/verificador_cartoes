# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('encodings')

a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('clients_colors.json', '.'),
        ('logo_rvb.png', '.'),
        ('main.py', '.'),
        ('config.py', '.'),
        ('rules.py', '.'),
        ('reader_pdf.py', '.'),
        ('extractor.py', '.'),
        ('classifier.py', '.'),
        ('grouper.py', '.'),
        ('exporter.py', '.'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VerificadorCartoesRVB',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
