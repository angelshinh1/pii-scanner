"""
Defines what a match looks like. 
"""

import re
from dataclasses import dataclass
from pii_scanner.luhn import luhn_valid

@dataclass(frozen=True)
class Finding:
    kind: str # Either SIN or CREDIT_CARD
    line: int # 1 based line number
    masked: str # XXX-XXX-123

SIN_RE = re.compile(r"(?<!\d)\d{3}([ -]?)\d{3}\1\d{3}(?!\d)")

def find_sins(line: str, line_no: int, skip: list | tuple = ()) -> list[Finding]:
    result = []
    for m in SIN_RE.finditer(line):
        if any(m.start() < end and start < m.end() for start, end in skip):
            continue
        digits = re.sub(r"\D", "", m.group())
        if not luhn_valid(digits):
            continue
        if digits[0] in "08":
            continue

        result.append(Finding("SIN", line_no, f"XXX-XXX-{digits[-3:]}"))
    return result

CARD_RE = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")

def card_prefix_ok(digits: str) -> bool:
    if digits[0] == '4': # visa
        return True
    if 51 <= int(digits[:2]) <= 55: # mastercard old range
        return True
    if 2221 <= int(digits[:4]) <= 2720: # mastercard 2 series
        return True
    if digits[:2] in ('34', '37'): # amex
        return True
    return False

def find_cards(line: str, line_no: int, spans: list | None = None) -> list[Finding]:
    result = []
    for m in CARD_RE.finditer(line):
        digits = re.sub(r"\D", "", m.group())
        if not 13 <= len(digits) <= 19:
            continue
        if not luhn_valid(digits):
            continue
        if not card_prefix_ok(digits):
            continue
        if spans is not None:
            spans.append(m.span())
        result.append(Finding("CREDIT_CARD", line_no, f"XXXX XXXX XXXX {digits[-4:]}"))

    return result

def detect(text: str) -> list[Finding]:
    result = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        card_spans = []
        result += find_cards(line, line_no, card_spans)
        result += find_sins(line, line_no, card_spans)
    return result
