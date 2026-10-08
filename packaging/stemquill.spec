# PyInstaller build for the standalone app:  pyinstaller packaging/stemquill.spec
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
IS_WIN = sys.platform.startswith("win")

datas = [(os.path.join(ROOT, "stemquill", "assets"), os.path.join("stemquill", "assets"))]
datas += collect_data_files("librosa")  # includes the .pyi stubs librosa's lazy loader needs

# librosa loads its modules lazily, so list them. Skip the parts Stemquill never uses
# (plotting, segmentation, decomposition): they pull in scikit-learn and matplotlib.
UNUSED = ("librosa.display", "librosa.segment", "librosa.decompose")
hidden = collect_submodules("librosa", filter=lambda name: not name.startswith(UNUSED))
hidden += collect_submodules("stemquill")
# Parts of the bundled libraries that only the optional chord add-on (basic-pitch) uses
hidden += ["scipy.io", "scipy.io.wavfile", "scipy.fftpack", "struct"]

a = Analysis(
    [os.path.join(SPECPATH, "launch.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=hidden,
    excludes=["matplotlib", "IPython", "pytest", "tensorflow", "torch", "basic_pitch",
              "sklearn", "pandas", "numba.tests", "llvmlite.tests", "setuptools", "pip"],
    noarchive=False,
)


def _not_tests(entry):
    """Drop the test suites that ship inside numpy, scipy and friends."""
    name = entry[0].replace("\\", "/")
    return not (".tests." in name or name.endswith(".tests") or "/tests/" in name)


a.pure = [e for e in a.pure if _not_tests(e)]
a.datas = [e for e in a.datas if _not_tests(e)]
a.binaries = [e for e in a.binaries if _not_tests(e)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Stemquill",
    console=False,
    strip=not IS_WIN,
    icon=os.path.join(ROOT, "stemquill", "assets", "stemquill.ico") if IS_WIN else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=not IS_WIN, name="Stemquill")
