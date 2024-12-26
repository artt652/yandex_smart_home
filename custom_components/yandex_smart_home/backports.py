"""Backports from newer Home Assistant versions."""

from enum import StrEnum


class LockState(StrEnum):
    """State of lock entities (2024.10+)."""

    JAMMED = "jammed"
    OPENING = "opening"
    LOCKING = "locking"
    OPEN = "open"
    UNLOCKING = "unlocking"
    LOCKED = "locked"
    UNLOCKED = "unlocked"
