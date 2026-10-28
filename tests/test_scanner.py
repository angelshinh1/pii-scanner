import json
from dataclasses import asdict

import pytest

from pii_scanner.scanner import MAX_SIZE, scan_folder


@pytest.fixture(autouse=True)
def allow_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("SCANNER_ALLOWED_ROOT", str(tmp_path))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_finds_sin_in_nested_file(tmp_path):
    write(tmp_path / "a" / "x.txt", "SIN 130 692 544")
    reports, scanned = scan_folder(tmp_path)
    assert scanned == 1
    assert reports[0].path == "a/x.txt"
    assert reports[0].counts == {"SIN": 1}


def test_counts_by_kind(tmp_path):
    write(tmp_path / "mixed.txt", "SIN 130 692 544\ncard 4111 1111 1111 1111\nSIN 123-456-782")
    reports, _ = scan_folder(tmp_path)
    assert reports[0].counts == {"SIN": 2, "CREDIT_CARD": 1}
    assert [f.line for f in reports[0].findings] == [1, 2, 3]


def test_clean_files_are_counted_but_not_returned(tmp_path):
    write(tmp_path / "clean.md", "nothing to see here")
    write(tmp_path / "dirty.txt", "SIN 130 692 544")
    reports, scanned = scan_folder(tmp_path)
    assert scanned == 2
    assert [r.path for r in reports] == ["dirty.txt"]


def test_skips_non_text_extensions(tmp_path):
    write(tmp_path / "data.bin", "SIN 130 692 544")
    write(tmp_path / "script.py", "SIN 130 692 544")
    reports, scanned = scan_folder(tmp_path)
    assert (reports, scanned) == ([], 0)


def test_skips_hidden_folders(tmp_path):
    write(tmp_path / ".git" / "log.txt", "SIN 130 692 544")
    write(tmp_path / ".venv" / "lib" / "notes.txt", "SIN 130 692 544")
    reports, scanned = scan_folder(tmp_path)
    assert (reports, scanned) == ([], 0)


def test_skips_large_files(tmp_path):
    write(tmp_path / "big.log", "SIN 130 692 544\n" + "x" * MAX_SIZE)
    reports, scanned = scan_folder(tmp_path)
    assert (reports, scanned) == ([], 0)


def test_non_recursive_only_scans_top_level(tmp_path):
    write(tmp_path / "top.txt", "SIN 130 692 544")
    write(tmp_path / "sub" / "deep.txt", "SIN 130 692 544")
    reports, _ = scan_folder(tmp_path, recursive=False)
    assert [r.path for r in reports] == ["top.txt"]


def test_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan_folder(tmp_path / "nope")


def test_file_instead_of_folder_raises(tmp_path):
    write(tmp_path / "x.txt", "hi")
    with pytest.raises(NotADirectoryError):
        scan_folder(tmp_path / "x.txt")


def test_refuses_path_outside_allowed_root(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setenv("SCANNER_ALLOWED_ROOT", str(allowed))
    with pytest.raises(PermissionError, match="outside the allowed scan root"):
        scan_folder(tmp_path)


def test_refuses_dotdot_escape(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setenv("SCANNER_ALLOWED_ROOT", str(allowed))
    with pytest.raises(PermissionError):
        scan_folder(allowed / "..")


def test_refuses_when_allowed_root_not_set(tmp_path, monkeypatch):
    monkeypatch.delenv("SCANNER_ALLOWED_ROOT")
    with pytest.raises(PermissionError, match="not set"):
        scan_folder(tmp_path)


def test_skips_symlink_pointing_outside_allowed_root(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    write(tmp_path / "secret.txt", "SIN 130 692 544")
    allowed.mkdir()
    try:
        (allowed / "link.txt").symlink_to(tmp_path / "secret.txt")
    except OSError:
        pytest.skip("symlinks not available on this system")
    monkeypatch.setenv("SCANNER_ALLOWED_ROOT", str(allowed))
    reports, scanned = scan_folder(allowed)
    assert (reports, scanned) == ([], 0)


def test_no_raw_value_leaks(tmp_path):
    raw_values = ["130692544", "123456782", "4111111111111111", "5555555555554444"]
    write(
        tmp_path / "hr" / "people.csv",
        "name,sin\nA,130 692 544\nB,123-456-782\n",
    )
    write(
        tmp_path / "finance" / "cards.txt",
        "visa 4111 1111 1111 1111 and mc 5555-5555-5555-4444",
    )
    reports, _ = scan_folder(tmp_path)
    assert sum(sum(r.counts.values()) for r in reports) == 4

    dumped = json.dumps([asdict(r) for r in reports])
    digits_only = "".join(ch for ch in dumped if ch.isdigit())
    for raw in raw_values:
        assert raw not in dumped
        assert raw not in digits_only
