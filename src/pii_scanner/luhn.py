"""
The Luhn checksum
Both SINs and credit cards use the same checksum. starting
from the rightmost digit, double every second digit and if
doubling gives more than 9, subtract 9. Add everything and
mod by 10. if 0 then its a valid number
"""

def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 != 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d

    return total%10 == 0
