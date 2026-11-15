"""Tests for the throttled progress log."""

import logging
import unittest

from opensiddur.common.progress import format_duration, progress

logger = logging.getLogger("opensiddur.tests.progress")


class FakeClock:
    """A clock that advances by ``step`` seconds each time it is read."""

    def __init__(self, step: float):
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        value = self.now
        self.now += self.step
        return value


class TestFormatDuration(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(format_duration(42.4), "42s")

    def test_minutes(self):
        self.assertEqual(format_duration(185), "3m05s")

    def test_hours(self):
        self.assertEqual(format_duration(3720), "1h02m")


class TestProgress(unittest.TestCase):
    def test_yields_the_items_unchanged(self):
        with self.assertLogs(logger, level="INFO"):
            self.assertEqual(list(progress(["a", "b"], "Checking", logger=logger)), ["a", "b"])

    def test_takes_an_iterable_without_a_length(self):
        with self.assertLogs(logger, level="INFO") as logs:
            items = list(progress((x for x in range(3)), "Checking", logger=logger))
        self.assertEqual(items, [0, 1, 2])
        self.assertEqual(logs.output[0], "INFO:opensiddur.tests.progress:Checking: 3 files")

    def test_start_and_end_lines_only_when_fast(self):
        with self.assertLogs(logger, level="INFO") as logs:
            list(progress(range(5), "Checking", logger=logger, clock=FakeClock(0.1)))
        self.assertEqual([r.getMessage() for r in logs.records],
                         ["Checking: 5 files", "Checking: 5 files done in 1s"])

    def test_a_line_each_interval(self):
        # The clock is read once at the start, once after each item and once at the end, so
        # each item takes 10 s and a 15 s interval logs after items 2 and 4 of 5.
        with self.assertLogs(logger, level="INFO") as logs:
            list(progress(range(5), "Checking", unit="project", logger=logger,
                          interval=15, clock=FakeClock(10)))
        self.assertEqual([r.getMessage() for r in logs.records], [
            "Checking: 5 projects",
            "Checking: 2/5 projects (40%), 20s elapsed, ~30s left",
            "Checking: 4/5 projects (80%), 40s elapsed, ~10s left",
            "Checking: 5 projects done in 1m00s",
        ])

    def test_no_intermediate_line_for_the_last_item(self):
        with self.assertLogs(logger, level="INFO") as logs:
            list(progress(range(1), "Checking", logger=logger, interval=1, clock=FakeClock(10)))
        self.assertEqual(len(logs.records), 2)

    def test_one_item_is_singular(self):
        with self.assertLogs(logger, level="INFO") as logs:
            list(progress(["a"], "Checking", unit="project", logger=logger))
        self.assertEqual(logs.records[0].getMessage(), "Checking: 1 project")

    def test_empty(self):
        with self.assertLogs(logger, level="INFO") as logs:
            self.assertEqual(list(progress([], "Checking", logger=logger)), [])
        self.assertEqual([r.getMessage() for r in logs.records][0], "Checking: 0 files")
        self.assertIn("0 files done", logs.records[-1].getMessage())


if __name__ == "__main__":
    unittest.main()
