# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

block_cipher = None

# Collect everything PyQt6 needs (datas, binaries, hiddenimports)
pyqt6_datas, pyqt6_binaries, pyqt6_hiddenimports = collect_all("PyQt6")

hiddenimports = []
hiddenimports += collect_submodules("matplotlib")
hiddenimports += collect_submodules("moa_actuator")
hiddenimports += pyqt6_hiddenimports

datas = []
datas += collect_data_files("matplotlib")
datas += collect_data_files("moa_actuator")
datas += pyqt6_datas
datas += [
    ("../../moa_actuator/config", "moa_actuator/config"),
    ("../../example/Dosa_2D_Solenoid", "example/Dosa_2D_Solenoid"),
]

a = Analysis(
    ["../../moa_actuator/gui_entry.py"],
    pathex=["../.."],
    binaries=pyqt6_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="moa_actuator_gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="moa_actuator_gui",
)
