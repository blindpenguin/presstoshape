# PyInstaller spec, run by scripts/build_package.py (which writes the generated inputs first).
# onedir on purpose: Qt stays in separate shared libraries (LGPL) and the same folder feeds ZIP, MSI and AppImage.
from pathlib import Path

ROOT = Path(SPECPATH).parent  # noqa: F821 - provided by PyInstaller
GENERATED = ROOT / "build" / "packaging"

analysis = Analysis(  # noqa: F821
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "presstoshape" / "assets"), "presstoshape/assets")],
    hiddenimports=["presstoshape._build_info"],
    # Pillow is a build-time tool (icon rendering) that PyInstaller would otherwise pick up.
    excludes=["tkinter", "PIL"],
)
pyz = PYZ(analysis.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="PressToShape",
    console=False,
    icon=str(GENERATED / "presstoshape.ico"),
    upx=False,
)
COLLECT(exe, analysis.binaries, analysis.datas, name="PressToShape", upx=False)  # noqa: F821
