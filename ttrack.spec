# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

# Collect all plotly data files (e.g., templates, configs, etc.)
plotly_data = collect_data_files("plotly")
hiddenimports = collect_submodules("plotly")

a = Analysis(
    ['src\\app.py'],
    pathex=[],
    binaries=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    datas=[
        ("icon_tt.ico", "."),
        ("icon_on.ico", "."),
        ("src/assets/i_table.png", "src/assets"),
        ("src/assets/i_stats.png", "src/assets"),
        ("src/assets/i_reload.png", "src/assets"),
        ("src/assets/i_edit.png", "src/assets"),
        *plotly_data
    ],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ttrack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon_tt.ico',
)
