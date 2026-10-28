#!/usr/bin/env python3
"""Gate daily GitHub triggers to alternate dates at fixed 05:00 UTC."""

from datetime import date, datetime, timezone
import os


ANCHOR = date(2026, 10, 28)


def is_due(event_name: str, now: datetime) -> bool:
    if event_name == "workflow_dispatch":
        return True
    if event_name != "schedule":
        return False
    if now.tzinfo is None:
        raise ValueError("A timezone-aware datetime is required")
    day = now.astimezone(timezone.utc).date()
    return (day - ANCHOR).days % 2 == 0


if __name__ == "__main__":
    due = is_due(os.environ.get("EVENT_NAME", ""), datetime.now(timezone.utc))
    print(f"due={str(due).lower()}")
