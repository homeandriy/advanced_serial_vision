from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent
a = Analysis([str(root / "tools" / "warehouse-server-entry.py")],
             pathex=[str(root / "application")],
             datas=collect_data_files("serial_vision") + collect_data_files("argon2"),
             excludes=["PySide6"])
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name="SerialVisionServer",console=True)
coll = COLLECT(exe,a.binaries,a.zipfiles,a.datas,name="SerialVisionServer")
