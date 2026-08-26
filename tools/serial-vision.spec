from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent
datas = (
    collect_data_files("serial_vision")
    + collect_data_files("rapidocr")
    + collect_data_files("tzdata")
)
a = Analysis([str(root / "application" / "serial_vision" / "main.py")], pathex=[str(root / "application")], datas=datas)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="SerialVision",
    icon=str(root / "application" / "serial_vision" / "assets" / "app-icon.ico"),
    console=False,
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name="SerialVision")
