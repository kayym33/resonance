"""Checks for the parts that run without a window.

Run from the repo root with:  python -m unittest discover tests

The data folder is pointed at a temporary directory before the app's
modules are imported, so nothing here reads or writes real data.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_ROOT = tempfile.mkdtemp(prefix="t1ld3-tests-")
os.environ["LOCALAPPDATA"] = DATA_ROOT
os.environ["HOME"] = DATA_ROOT
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from resonance.battery import Battery, LowBatteryWatch  # noqa: E402
from resonance.launcher import Command, suggest  # noqa: E402
from resonance.store import Collection  # noqa: E402
from resonance.usage import (  # noqa: E402
    HALF_LIFE_DAYS,
    Usage,
    frecency,
    load_usage,
    record_use,
)

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def used(count: int, days_ago: float = 0) -> Usage:
    return Usage(count, NOW - timedelta(days=days_ago))


def command(name: str, description: str = "", *aliases: str) -> Command:
    return Command(name, description, (("true",),), tuple(aliases))


COMMANDS = [
    command("zen", "Zen browser"),
    command("zed", "editor"),
    command("zip", "archive tool"),
    command("term", "terminal"),
]


def titles(text: str, usage: dict[str, Usage] | None = None) -> list[str]:
    return [item.title for item in suggest(text, COMMANDS, usage=usage, now=NOW)]


class FrecencyTests(unittest.TestCase):
    def test_unused_scores_zero(self) -> None:
        self.assertEqual(frecency(None, NOW), 0)

    def test_more_uses_score_higher(self) -> None:
        self.assertGreater(frecency(used(10), NOW), frecency(used(2), NOW))

    def test_recent_uses_score_higher(self) -> None:
        self.assertGreater(frecency(used(5, 1), NOW), frecency(used(5, 30), NOW))

    def test_score_halves_each_half_life(self) -> None:
        self.assertAlmostEqual(
            frecency(used(7, HALF_LIFE_DAYS), NOW),
            frecency(used(7), NOW) / 2,
        )

    def test_new_habit_beats_stale_favourite(self) -> None:
        self.assertGreater(frecency(used(3), NOW), frecency(used(100, 60), NOW))

    def test_clock_set_back_is_harmless(self) -> None:
        self.assertEqual(frecency(used(3, -5), NOW), frecency(used(3), NOW))


class SuggestTests(unittest.TestCase):
    def test_without_usage_keeps_file_order(self) -> None:
        self.assertEqual(titles("z")[:3], ["zen", "zed", "zip"])

    def test_usage_orders_equal_matches(self) -> None:
        usage = {"zip": used(9), "zed": used(2)}
        self.assertEqual(titles("z", usage)[:3], ["zip", "zed", "zen"])

    def test_recency_orders_equal_counts(self) -> None:
        usage = {"zen": used(4, 40), "zip": used(4, 1)}
        self.assertEqual(titles("z", usage)[:2], ["zip", "zen"])

    def test_usage_never_beats_a_better_match(self) -> None:
        # "zip" is used constantly, but "ze" is a prefix of zen and zed only.
        usage = {"zip": used(1000), "term": used(1000)}
        self.assertEqual(titles("ze", usage)[:2], ["zen", "zed"])
        # An exact name beats a heavily used prefix match.
        commands = [command("zen"), command("zenith")]
        result = suggest("zen", commands, usage={"zenith": used(1000)}, now=NOW)
        self.assertEqual([item.title for item in result], ["zen", "zenith"])
        # A name match beats a heavily used description match.
        self.assertEqual(titles("ter", {"zen": used(1000)})[0], "term")

    def test_builtins_rank_with_commands(self) -> None:
        # "t": term (command), todo and theme (built-ins) all match by prefix.
        self.assertEqual(titles("t")[:3], ["term", "todo", "theme"])
        self.assertEqual(titles("t", {"theme": used(5)})[:3], ["theme", "term", "todo"])

    def test_builtins_still_suggested(self) -> None:
        for name in ("player", "play", "todo", "cal", "home", "account", "theme", "quit"):
            with self.subTest(name=name):
                first = suggest(name, COMMANDS, usage={"zen": used(1000)}, now=NOW)[0]
                self.assertEqual(first.title, name)
        self.assertEqual(suggest("play some song", COMMANDS)[0].kind, "play")
        self.assertEqual(suggest("todo buy milk", COMMANDS)[0].kind, "todo")
        self.assertEqual(suggest("= 6*7", COMMANDS)[0].args, "42")


class UsageStoreTests(unittest.TestCase):
    def test_record_use_counts_and_stamps(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "usage.json"
            collection = Collection("usage", path)
            record_use("zen", collection)
            record_use("zen", collection)
            record_use("term", collection)
            usage = load_usage(Collection("usage", path))  # Re-read from disk.
            self.assertEqual(usage["zen"].count, 2)
            self.assertEqual(usage["term"].count, 1)
            age = datetime.now(timezone.utc) - usage["zen"].last_used
            self.assertLess(abs(age.total_seconds()), 60)

    def test_damaged_records_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            collection = Collection("usage", Path(folder) / "usage.json")
            collection.put("bad", {"count": "many"})
            collection.put("good", {"count": 1, "last_used": NOW.isoformat()})
            self.assertEqual(list(load_usage(collection)), ["good"])


class LowBatteryTests(unittest.TestCase):
    def warnings(self, readings: list[Battery | None]) -> list[bool]:
        watch = LowBatteryWatch()
        return [watch.update(reading) for reading in readings]

    def test_warns_once_under_twenty(self) -> None:
        readings = [Battery(p, False) for p in (22, 20, 19, 18, 17)]
        self.assertEqual(self.warnings(readings), [False, False, True, False, False])

    def test_no_flicker_around_twenty(self) -> None:
        readings = [Battery(p, False) for p in (19, 21, 19, 25, 19)]
        self.assertEqual(self.warnings(readings), [True, False, False, False, False])

    def test_rearms_above_twenty_five(self) -> None:
        readings = [Battery(p, False) for p in (19, 26, 19)]
        self.assertEqual(self.warnings(readings), [True, False, True])

    def test_rearms_after_charging(self) -> None:
        readings = [Battery(15, False), Battery(15, True), Battery(15, False)]
        self.assertEqual(self.warnings(readings), [True, False, True])

    def test_quiet_while_charging_or_without_battery(self) -> None:
        self.assertEqual(self.warnings([Battery(5, True), None]), [False, False])

    def test_still_low(self) -> None:
        self.assertTrue(LowBatteryWatch.still_low(Battery(23, False)))
        self.assertFalse(LowBatteryWatch.still_low(Battery(26, False)))
        self.assertFalse(LowBatteryWatch.still_low(Battery(10, True)))
        self.assertFalse(LowBatteryWatch.still_low(None))


if __name__ == "__main__":
    unittest.main()
