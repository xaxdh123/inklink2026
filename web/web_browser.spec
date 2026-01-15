# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for web browser application.

Build command:
    pyinstaller web_browser.spec

This will create an executable at:
    dist/web_browser.exe
"""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['web_app.py'],
    pathex=[str(Path(__file__).parent)],
    binaries=[],
    datas=[
        ('web_profile.py', '.'),
        ('web_browser_widget.py', '.'),
    ],
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'pyqtdarktheme',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
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
    name='web_browser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
