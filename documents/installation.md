# Windows installation and updates

Serial Vision is packaged as a self-contained 64-bit Windows executable and an
Inno Setup installer. The installer contains no API keys, images, SQLite database,
or user settings.

- The installer is localized in Ukrainian, English and Polish. It proposes the
  Windows UI language and lets the administrator change it.
- User data remains in the Windows per-user app-data directory, outside Program
  Files. Updates replace only application files; uninstall also preserves data.
- The installer requests application shutdown when an earlier executable is open.
- Build with `tools/build-release.ps1 -Version <VERSION>` after tests pass. It
  produces the PyInstaller executable first and compiles `installer/serial-vision.iss`
  with Inno Setup.
