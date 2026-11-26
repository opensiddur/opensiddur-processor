"""The distribution notice and the back-page statement, as the output stages share them.

What they say is in the settings file's `distribution` section (settings.DistributionSettings);
each output stage only serialises it. The printed book takes the back notice's `print`
statements, the electronic book its `electronic` ones.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Literal

from opensiddur.exporter.settings import (
    DEFAULT_LOGO,
    DistributionNotice,
    DistributionSettings,
)

#: The Open Siddur Project's logo, carried with the exporter.
OPEN_SIDDUR_LOGO = Path(__file__).parent / "assets" / "open-siddur-logo.png"

Medium = Literal["electronic", "print"]


class RunKind(StrEnum):
    TEXT = "text"
    EMPHASIS = "emphasis"
    URL = "url"


_URL = re.compile(r"https?://\S+")
# Emphasis is marked at word boundaries, so that the underscores in snake_case are not marks.
_EMPHASIS = re.compile(r"(?<!\w)_(?P<emphasis>[^_\s](?:[^_]*[^_\s])?)_(?!\w)")


def _url_end(url: str) -> int:
    """Where a URL found running to the next space really ends: a sentence's closing
    punctuation is not part of it, nor a closing parenthesis that the URL did not open."""
    end = len(url)
    while end and (url[end - 1] in ".,;:!?"
                   or (url[end - 1] == ")" and url.count("(", 0, end) < url.count(")", 0, end))):
        end -= 1
    return end


def _emphasis_runs(text: str) -> list[tuple[RunKind, str]]:
    runs: list[tuple[RunKind, str]] = []
    position = 0
    for match in _EMPHASIS.finditer(text):
        if match.start() > position:
            runs.append((RunKind.TEXT, text[position:match.start()]))
        runs.append((RunKind.EMPHASIS, match.group("emphasis")))
        position = match.end()
    if position < len(text):
        runs.append((RunKind.TEXT, text[position:]))
    return runs


def notice_runs(text: str) -> list[tuple[RunKind, str]]:
    """A line of a notice as runs of plain text, `_emphasis_` and URLs. A URL is never
    emphasised, nor read for emphasis marks."""
    runs: list[tuple[RunKind, str]] = []
    position = 0
    for match in _URL.finditer(text):
        end = match.start() + _url_end(match.group())
        runs += _emphasis_runs(text[position:match.start()])
        runs.append((RunKind.URL, text[match.start():end]))
        position = end
    runs += _emphasis_runs(text[position:])
    # Adjacent text runs (around a URL that was all punctuation) are one run.
    merged: list[tuple[RunKind, str]] = []
    for kind, run in runs:
        if merged and kind is RunKind.TEXT and merged[-1][0] is RunKind.TEXT:
            merged[-1] = (kind, merged[-1][1] + run)
        elif run:
            merged.append((kind, run))
    return merged


def distribution_notice(distribution: DistributionSettings) -> DistributionNotice | None:
    """The notice the book carries, or None if it carries none."""
    notice = distribution.notice
    return None if notice == "none" else notice


def resolve_logo(notice: DistributionNotice, settings_file: Path | None) -> Path | None:
    """The notice's logo, as an absolute path; None if it has none.

    A path is relative to the settings file that names it (to the working directory when
    there is no file). A logo that is not there is an error: a notice without the logo it
    asked for is not the notice that was asked for.
    """
    if notice.logo == "none":
        return None
    if notice.logo == DEFAULT_LOGO:
        return OPEN_SIDDUR_LOGO
    base = Path(settings_file).resolve().parent if settings_file is not None else Path.cwd()
    logo = (base / notice.logo).resolve()
    if not logo.is_file():
        raise FileNotFoundError(f"distribution notice logo {notice.logo!r} not found at {logo}")
    return logo


def back_notice_items(distribution: DistributionSettings, medium: Medium) -> list[str]:
    """The back page's statements for this kind of book; none if it has no back page."""
    back = distribution.back_notice
    if back == "none":
        return []
    return list(getattr(back, medium))
