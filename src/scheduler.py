"""
Scheduling engine for TikTok fleet daemon.

Per-phone posting slots are derived from source channel posting history,
then jittered +/-10% to avoid synchronized batch posting across the fleet.
"""
import random
import re
from datetime import datetime, timedelta

WARMUP_TAG = "ngam"
DEFAULT_INTERVAL_HOURS = 8


def get_interval_hours(phone: dict) -> int:
    """
    Read posting interval from Geelark tags (e.g. '8h', '12h').
    Falls back to DEFAULT_INTERVAL_HOURS if no tag found.
    """
    tags = phone.get("tags") or []
    for tag in tags:
        name = tag.get("name", "") if isinstance(tag, dict) else tag
        match = re.fullmatch(r"([1-9]|1[0-9]|2[0-4])h", name)
        if match:
            return int(match.group(1))
    return DEFAULT_INTERVAL_HOURS


def is_warmup(phone: dict) -> bool:
    """Check if a phone is in warmup state (tagged 'ngam')."""
    tags = phone.get("tags") or []
    for tag in tags:
        name = tag.get("name", "") if isinstance(tag, dict) else tag
        if name == WARMUP_TAG:
            return True
    return False


def has_group(phone: dict) -> bool:
    """Check if a phone has a group assigned."""
    return bool(phone.get("group", {}).get("name"))


def next_post_time(last_post: datetime | None, interval_hours: int) -> datetime:
    """
    Returns the next post time: last_post + interval * jitter.
    Jitter is uniform in [0.9, 1.1].
    If last_post is None, returns now.
    """
    if last_post is None:
        return datetime.now()
    jitter = random.uniform(0.9, 1.1)
    delta = timedelta(hours=interval_hours) * jitter
    candidate = last_post + delta
    return max(candidate, datetime.now())


def is_eligible(phone: dict, temporarily_blocked: set) -> bool:
    """Check if a phone is eligible for posting."""
    return (
        has_group(phone)
        and not is_warmup(phone)
        and phone.get("serialNo") not in temporarily_blocked
    )


def filter_eligible(phones: list, temporarily_blocked: set) -> list:
    """Filter phones to only eligible ones."""
    return [p for p in phones if is_eligible(p, temporarily_blocked)]