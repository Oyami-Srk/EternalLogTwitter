import re
from datetime import timedelta

SECONDS_PER = {
    's': 1,
    'm': 60,
    'h': 60 * 60,
    'd': 60 * 60 * 24,
    'w': 60 * 60 * 24 * 7,
    'M': 60 * 60 * 24 * 30,
    'y': 60 * 60 * 24 * 365,
}


def parse_human_date(date: str) -> timedelta:
    match = re.match(r"(\d+)([smhdwMy])", date)
    if not match:
        raise ValueError(f"Invalid date format: {date}")
    amount, unit = match.groups()
    return timedelta(seconds=int(amount) * SECONDS_PER[unit])
