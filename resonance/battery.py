"""The computer's own battery, if it has one.

Returns None on machines without a system battery (desktops), so the UI
can leave the battery out entirely. Uses only the standard library.
"""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path

POWER_SUPPLY_DIR = Path("/sys/class/power_supply")
LOW_PERCENT = 20
# The one-time warning: shown under the first, re-armed above the second.
WARN_BELOW_PERCENT = 20
REARM_ABOVE_PERCENT = 25


@dataclass(frozen=True)
class Battery:
    percent: int
    charging: bool

    @property
    def low(self) -> bool:
        return self.percent <= LOW_PERCENT and not self.charging


class LowBatteryWatch:
    """Decides when to warn that the battery is running low.

    Warns once each time the charge drops under WARN_BELOW_PERCENT while
    unplugged, then stays quiet until the laptop has been plugged in or
    the charge has climbed back over REARM_ABOVE_PERCENT. The gap between
    the two keeps it from repeating while the charge hovers around 20%.
    """

    def __init__(self) -> None:
        self.armed: bool = True

    def update(self, battery: Battery | None) -> bool:
        """Take the latest reading; True means "show the warning now"."""
        if battery is None or battery.charging:
            self.armed = True
            return False
        if battery.percent > REARM_ABOVE_PERCENT:
            self.armed = True
            return False
        if battery.percent < WARN_BELOW_PERCENT and self.armed:
            self.armed = False
            return True
        return False

    @staticmethod
    def still_low(battery: Battery | None) -> bool:
        """Whether a warning already on screen should stay there."""
        return (
            battery is not None
            and not battery.charging
            and battery.percent <= REARM_ABOVE_PERCENT
        )


def read_battery() -> Battery | None:
    try:
        if os.name == "nt":
            return read_windows_battery()
        return read_linux_battery()
    except (OSError, ValueError, AttributeError):
        return None


def read_linux_battery() -> Battery | None:
    percents: list[int] = []
    charging = False
    for supply in POWER_SUPPLY_DIR.glob("*"):
        if read_text(supply / "type") != "Battery":
            continue
        # Wireless mice, keyboards and headsets report scope "Device";
        # only the machine's own batteries count.
        if read_text(supply / "scope") == "Device":
            continue
        capacity = read_text(supply / "capacity")
        if not capacity:
            continue
        percents.append(int(capacity))
        charging = charging or read_text(supply / "status") in ("Charging", "Full")
    if not percents:
        return None
    return Battery(round(sum(percents) / len(percents)), charging)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


class SystemPowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


NO_SYSTEM_BATTERY = 128
UNKNOWN = 255


def read_windows_battery() -> Battery | None:
    status = SystemPowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return None
    if (
        status.BatteryFlag == UNKNOWN
        or status.BatteryFlag & NO_SYSTEM_BATTERY
        or status.BatteryLifePercent == UNKNOWN
    ):
        return None
    return Battery(status.BatteryLifePercent, status.ACLineStatus == 1)


def describe(battery: Battery) -> str:
    """Like "[###··] 70%", with "+" while charging."""
    filled = round(battery.percent / 20)
    bar = "#" * filled + "·" * (5 - filled)
    return f"[{bar}] {battery.percent}%{' +' if battery.charging else ''}"
