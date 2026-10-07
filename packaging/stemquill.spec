# PyInstaller build for the standalone app:  pyinstaller packaging/stemquill.spec
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
IS_WIN = sys.platform.startswith("win")

datas = [(os.path.join(ROOT, "stemquill", "assets"), os.path.join("stemquill", "assets"))]
datas += collect_data_files("librosa")  # includes the .pyi stubs librosa's lazy loader needs
hidden = collect_submodules("librosa") + collect_submodules("stemquill") + ["sklearn.utils._typedefs"]

a = Analysis(
    [os.path.join(SPECPATH, "launch.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=hidden,
    excludes=["matplotlib", "IPython", "pytest", "tensorflow", "torch", "basic_pitch"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Stemquill",
    console=False,
    icon=os.path.join(ROOT, "stemquill", "assets", "stemquill.ico") if IS_WIN else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Stemquill")
