"""Throttled progress lines for long loops, so a CI log shows a slow step is still moving.

A validator that reports only failures is silent for as long as it runs, and in a CI log a step
that is slow looks the same as one that is hung. :func:`progress` wraps the loop and logs a line
at the start, one at most every ``interval`` seconds while it runs (count, percent, elapsed time
and an estimate of what is left), and one at the end. It logs through the caller's logger at
INFO, so it goes wherever the CLI's ``logging.basicConfig`` sends it (stderr) and leaves the
report on stdout alone; under the test runner, where nothing configures logging, it is silent.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Iterable, Iterator, TypeVar

T = TypeVar("T")


def format_duration(seconds: float) -> str:
    """``42s``, ``3m05s`` or ``1h02m``."""
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def progress(
    items: Iterable[T],
    what: str,
    *,
    logger: logging.Logger,
    unit: str = "file",
    interval: float = 15.0,
    clock: Callable[[], float] = time.monotonic,
) -> Iterator[T]:
    """Yield each of ``items`` unchanged, logging how far through them the loop is."""
    if not hasattr(items, "__len__"):
        items = list(items)
    total = len(items)  # type: ignore[arg-type]
    units = unit if total == 1 else f"{unit}s"
    logger.info("%s: %d %s", what, total, units)

    start = last = clock()
    done = 0
    for item in items:
        yield item
        done += 1
        now = clock()
        if done < total and now - last >= interval:
            last = now
            elapsed = now - start
            left = elapsed / done * (total - done)
            logger.info(
                "%s: %d/%d %s (%d%%), %s elapsed, ~%s left",
                what, done, total, units, 100 * done // total,
                format_duration(elapsed), format_duration(left),
            )
    logger.info("%s: %d %s done in %s", what, done, units, format_duration(clock() - start))
