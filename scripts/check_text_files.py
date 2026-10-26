"""Require UTF-8 without BOM and LF in every tracked text file or staged blob."""

from __future__ import annotations

import argparse
import io
import subprocess
from pathlib import Path


def git(*arguments: str, data: bytes | None = None) -> bytes:
    return subprocess.check_output(["git", *arguments], input=data)


def violations(data: bytes) -> list[str]:
    problems = []
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        problems.append("not UTF-8")
    if data.startswith(b"\xef\xbb\xbf"):
        problems.append("UTF-8 BOM")
    if b"\0" in data:
        problems.append("NUL in text file")
    if b"\r" in data:
        problems.append("CRLF or CR instead of LF")
    return problems


def check(staged: bool = False) -> int:
    root = Path(git("rev-parse", "--show-toplevel").decode().strip())
    records = []
    for entry in git("ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, oid, stage = metadata.split()
        if stage != b"0":
            raise RuntimeError("Resolve index conflicts before checking text files")
        if mode not in (b"120000", b"160000"):
            records.append((name.decode("utf-8"), oid))
    names = b"\0".join(name.encode("utf-8") for name, _ in records) + b"\0"
    attributes = git("check-attr", "-z", "--stdin", "text", data=names).split(b"\0")
    binary = {
        attributes[i].decode("utf-8")
        for i in range(0, len(attributes) - 2, 3)
        if attributes[i + 2] == b"unset"
    }
    blobs = {}
    if staged:
        ids = list(dict.fromkeys(oid for _, oid in records))
        stream = io.BytesIO(git("cat-file", "--batch", data=b"\n".join(ids) + b"\n"))
        for oid in ids:
            header = stream.readline().split()
            if len(header) != 3 or header[1] != b"blob":
                raise RuntimeError("Cannot read staged blob")
            blobs[oid] = stream.read(int(header[2]))
            if stream.read(1) != b"\n":
                raise RuntimeError("Invalid Git batch response")
    checked, failed = 0, False
    for name, oid in records:
        if name in binary:
            continue
        data = blobs[oid] if staged else (root / name).read_bytes()
        # Git's auto-text heuristic; explicitly marked text must always decode.
        if b"\0" in data:
            explicit = any(
                attributes[i] == name.encode("utf-8") and attributes[i + 2] == b"set"
                for i in range(0, len(attributes) - 2, 3)
            )
            if not explicit:
                continue
        checked += 1
        problems = violations(data)
        if problems:
            print(f"{name}: {', '.join(problems)}")
            failed = True
    if not failed:
        print(f"Checked {checked} text files: UTF-8 without BOM, LF.")
    return int(failed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staged", action="store_true", help="Check index blobs rather than the working tree"
    )
    arguments = parser.parse_args()
    return check(arguments.staged)


if __name__ == "__main__":
    raise SystemExit(main())
