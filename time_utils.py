"""Timezone helpers for UI, logs, and reports."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Kolkata")
COMMON_TIMEZONES = [
    "Asia/Kolkata",
    "Asia/Dubai",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Europe/London",
    "Europe/Berlin",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "Australia/Sydney",
]


def sanitize_timezone(tz_name: str | None) -> str:
    tz_name = str(tz_name or "").strip() or DEFAULT_TIMEZONE
    try:
        ZoneInfo(tz_name)
        return tz_name
    except Exception:
        return DEFAULT_TIMEZONE


def tz_label(tz_name: str | None) -> str:
    tz_name = sanitize_timezone(tz_name)
    return tz_name.split("/")[-1].replace("_", " ")


def _coerce_dt(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("T", " ")
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text[: len(fmt.replace('%f', '000000'))], fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def format_db_timestamp(value, tz_name: str | None = None, fmt: str = "%d %b %Y, %I:%M %p", include_zone: bool = True) -> str:
    dt = _coerce_dt(value)
    if not dt:
        return str(value or "")
    tz_name = sanitize_timezone(tz_name)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone(ZoneInfo(tz_name))
    rendered = local_dt.strftime(fmt)
    return f"{rendered} {tz_label(tz_name)}" if include_zone else rendered


def format_db_time(value, tz_name: str | None = None) -> str:
    return format_db_timestamp(value, tz_name=tz_name, fmt="%I:%M %p", include_zone=False)


def format_now(tz_name: str | None = None, fmt: str = "%d %b %Y, %I:%M %p", include_zone: bool = True) -> str:
    tz_name = sanitize_timezone(tz_name)
    now_local = datetime.now(ZoneInfo(tz_name))
    rendered = now_local.strftime(fmt)
    return f"{rendered} {tz_label(tz_name)}" if include_zone else rendered


def format_appt_slot(appt_date, appt_time, tz_name: str | None = None, include_zone: bool = True) -> str:
    if not appt_date and not appt_time:
        return "—"
    tz_name = sanitize_timezone(tz_name)
    text = f"{appt_date or '—'} {appt_time or '—'}".strip()
    return f"{text} {tz_label(tz_name)}" if include_zone else text
