"""Generate the standalone updater's embedded catalog from the application's TEXT."""

from __future__ import annotations

import argparse
import ast
import pprint
import subprocess
import sys
from pathlib import Path

from serial_vision.i18n import SUPPORTED_LOCALES, TEXT


def render(source: str, filename: str) -> str:
    tree = ast.parse(source)
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "UPDATER_TEXT" for target in node.targets
        )
    )
    if assignment.end_lineno is None:
        raise RuntimeError("Cannot locate embedded updater catalog")
    catalog = {
        language: {
            key: value for key, value in TEXT[language].items() if key.startswith("updater_")
        }
        for language in SUPPORTED_LOCALES
    }
    lines = source.splitlines(keepends=True)
    generated = (
        "".join(lines[: assignment.lineno - 1])
        + "UPDATER_TEXT = "
        + pprint.pformat(catalog, width=100, sort_dicts=False)
        + "\n"
        + "".join(lines[assignment.end_lineno :])
    )
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--stdin-filename", filename, "-"],
        input=generated,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail if generation would change the updater"
    )
    arguments = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / "tools" / "advance_serial_vision_path_updater.py"
    source = path.read_text(encoding="utf-8")
    generated = render(source, str(path))
    if generated == source:
        print("Standalone updater translations are current.")
        return 0
    if arguments.check:
        print(
            "Standalone updater translations are stale; run make updater-translations.",
            file=sys.stderr,
        )
        return 1
    path.write_text(generated, encoding="utf-8", newline="\n")
    print(f"Generated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
