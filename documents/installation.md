# Windows installation and updates

Advanced Serial Vision is packaged as a self-contained 64-bit Windows executable and an
Inno Setup installer. The installer contains no API keys, images, SQLite database,
or user settings.

- The Inno Setup installer is localized in Ukrainian, English and Polish. It
  proposes the Windows UI language and lets the administrator change it. MSI is
  published as three separate UI-localized files with `-uk`, `-en` and `-pl`
  suffixes; choose the needed language before starting it.
- Python/Qt installer files are placed in `Program Files\Advanced Serial Vision`,
  separately from the original NativePHP application.
- User data is stored separately at the current user's `AppData` location for
  `homeandriy\Advanced Serial Vision`, outside Program Files and separate from
  the previous application. Updates replace only application files; uninstall
  also preserves data.
- The installer requests application shutdown when an earlier executable is open.
- Build with `tools/build-release.ps1 -Version <VERSION>` after tests pass. It
  produces the PyInstaller executable first and compiles `installer/serial-vision.iss`
  with Inno Setup.
