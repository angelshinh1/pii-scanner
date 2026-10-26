import pytest
from pii_scanner.detectors import detect


@pytest.mark.parametrize("text,expected", [
    ("SIN: 130 692 544", 1), # spaces
    ("SIN: 130-692-544", 1), # dashes
    ("SIN: 130692544", 1), # no separators
    ("SIN: 130-692-545", 0), # bad checksum
    ("SIN: 046 454 286", 0), # leading 0 (passes Luhn,fictitious)
    ("SIN: 830 692 547", 0), # leading 8 (passes Luhn, notissued)
    ("SIN: 930 692 546", 1), # leading 9 (temporary resident,keep)
    ("Call 416-555-1234", 0), # 10-digit phone number
    ("Order #1306925440", 0), # SIN digits inside a longernumber
    ("card 410 811 111 111 1116", 0), # card whose first 9 digits look like a SIN
])
def test_sin_detection(text, expected):
    found = [f for f in detect(text) if f.kind == "SIN"]
    assert len(found) == expected


@pytest.mark.parametrize("text,expected", [
    ("card 4111 1111 1111 1111", 1), # Visa, spaces
    ("card 4111-1111-1111-1111", 1), # Visa, dashes
    ("card 5555555555554444", 1), # Mastercard
    ("card 378282246310005", 1), # Amex
    ("card 4111 1111 1111 1112", 0), # bad checksum
    ("card 410 811 111 111 1116", 1), # still found as a card
])
def test_card_detection(text, expected):
    found = [f for f in detect(text) if f.kind == "CREDIT_CARD"]
    assert len(found) == expected


@pytest.mark.parametrize("text,raw", [
    ("SIN: 130 692 544", "130692544"),
    ("card 4111 1111 1111 1111", "4111111111111111"),
])
def test_masked_never_contains_full_number(text, raw):
    found = detect(text)
    assert found  # make sure something was actually detected
    for f in found:
        assert raw not in f.masked.replace(" ", "").replace("-", "")