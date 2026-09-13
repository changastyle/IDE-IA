# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['ng-studio-app.py'],
    pathex=['.'],
    binaries=[],
    datas=[('UI', 'UI'), ('Skills-py', 'Skills-py'), ('Voice', 'Voice'), ('utils', 'utils'), ('iconos', 'iconos'), ('splash', 'splash'), ('conversaciones', 'conversaciones'), ('README', 'README'), ('CI-CD-LOCAL/version-macos.md', 'CI-CD-LOCAL')],
    hiddenimports=['PySide6.QtWidgets', 'PySide6.QtCore', 'PySide6.QtGui', 'requests', 'pyte', 'pyte.streams'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='NG-STUDIO',
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
)
app = BUNDLE(
    exe,
    name='NG-STUDIO.app',
    icon=None,
    bundle_identifier=None,
)
