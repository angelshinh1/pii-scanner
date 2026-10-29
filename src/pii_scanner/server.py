"""
MCP server for the scanner. Never print() here: with stdio transport,
stdout carries the protocol. Logging goes to stderr.
"""

import logging
from dataclasses import asdict
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from pii_scanner import scanner

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pii_scanner.server")

mcp = FastMCP("pii-scanner")


def totals(reports: list[scanner.FileReport]) -> dict[str, int]:
    result = {}
    for r in reports:
        for kind, n in r.counts.items():
            result[kind] = result.get(kind, 0) + n
    return result


@mcp.tool
def scan_folder(path: str, recursive: bool = True) -> dict:
    """Scan a folder for Canadian SINs and credit card numbers.

    Only .txt, .csv, .md, .log and .json files are scanned. Hidden folders
    and files over 5 MB are skipped. The path must be inside the allowed
    scan root.

    Returns a summary (files scanned, files flagged, totals by kind) and a
    report per flagged file with 1-based line numbers and masked values
    like XXX-XXX-544. Never returns file contents or full numbers.
    """
    try:
        reports, scanned = scanner.scan_folder(Path(path), recursive)
    except OSError as e:
        raise ToolError(str(e)) from None

    log.info("scan_folder scanned=%d flagged=%d", scanned, len(reports))
    return {
        "root": Path(path).resolve().as_posix(),
        "files_scanned": scanned,
        "files_flagged": len(reports),
        "totals": totals(reports),
        "reports": [asdict(r) for r in reports],
    }


@mcp.tool
def scan_file(path: str) -> dict:
    """Scan a single file for Canadian SINs and credit card numbers.

    The file must be a .txt, .csv, .md, .log or .json file under 5 MB,
    inside the allowed scan root.

    Returns per-kind counts and findings with 1-based line numbers and
    masked values like XXXX XXXX XXXX 1111. Never returns file contents
    or full numbers.
    """
    try:
        allowed = scanner.allowed_root()
        file = Path(path).resolve()
        if not file.is_relative_to(allowed):
            raise PermissionError(f"Path is outside the allowed scan root {allowed.as_posix()}")
        if not file.is_file():
            raise FileNotFoundError(f"File not found: {file.as_posix()}")
        if file.suffix.lower() not in scanner.ALLOWED_SUFFIXES:
            allowed_list = ", ".join(sorted(scanner.ALLOWED_SUFFIXES))
            raise ValueError(f"Unsupported file type {file.suffix!r}. Supported: {allowed_list}")
        if file.stat().st_size > scanner.MAX_SIZE:
            raise ValueError("File is larger than 5 MB and was not scanned")
        report = scanner.scan_file(file, allowed)
    except (OSError, ValueError) as e:
        raise ToolError(str(e)) from None

    log.info("scan_file findings=%d", len(report.findings))
    return asdict(report)


if __name__ == "__main__":
    # The banner also runs an update check against PyPI
    mcp.run(show_banner=False)
