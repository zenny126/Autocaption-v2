# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('AutoCaption.css', '.')] + collect_data_files('demucs'),
    hiddenimports=['numpy', 'numpy.core', 'numpy.core.multiarray', 'numpy._core'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['sqlite3', 'win32com', 'pythonwin', 'google', 'markupsafe', 'jinja2', 'fsspec'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WhisperSubtitler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WhisperSubtitler',
)
