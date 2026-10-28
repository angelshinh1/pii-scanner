from pii_scanner.detectors import Finding
from pii_scanner.detectors import detect
from dataclasses import dataclass
from pathlib import Path
import os

@dataclass
class FileReport:
    path: str # relative to scan root, forward slashes
    counts: dict[str, int] # {"SIN": 3, "CREDIT_CARD": 4}
    findings: list[Finding]

def scan_file(path: Path, root: Path) -> FileReport:
    file = path.read_text(encoding='utf-8', errors='replace')
    detected = detect(file)

    counts ={}
    for f in detected:
        counts[f.kind] = counts.get(f.kind, 0) + 1

    return FileReport(path.relative_to(root).as_posix(), counts, detected)

ALLOWED_SUFFIXES = {'.txt', '.csv', '.md', '.log', '.json'}
MAX_SIZE = 5 * 1024 * 1024 # 5 mb
def allowed_root() -> Path:
    allowed = os.environ.get("SCANNER_ALLOWED_ROOT")
    if not allowed:
        raise PermissionError("SCANNER_ALLOWED_ROOT is not set")
    return Path(allowed).resolve()

def scan_folder(root: Path, recursive: bool = True) -> tuple[list[FileReport], int]:
    root = root.resolve()
    allowed = allowed_root()
    if not root.is_relative_to(allowed):
        raise PermissionError(f"Path is outside the allowed scan root {allowed.as_posix()}")
    if not root.exists():
        raise FileNotFoundError(f"Folder not found: {root.as_posix()}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a folder: {root.as_posix()}")

    files = sorted(root.rglob("*") if recursive else root.glob("*"))

    reports = []
    scanned = 0
    for path in files:
        if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts[:-1]):
            continue
        if not path.resolve().is_relative_to(allowed):
            continue
        if path.stat().st_size > MAX_SIZE:
            continue

        scanned += 1
        report = scan_file(path, root)
        if report.findings:
            reports.append(report)

    return reports, scanned
