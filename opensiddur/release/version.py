"""Version parsing and bumping.

Below 1.0.0 a release bumps the minor version by default, or the patch version for a
release that only fixes bugs, and backwards compatibility is not promised. From 1.0.0 on the project follows semantic versioning strictly, so the bump
level must be chosen deliberately rather than defaulted.

Between releases, main is the development of the next one: `0.7.0.dev0` after 0.6.0 is
released. That is what lets a settings file that needs what main has (`requires_processor:
">=0.7.0"`) be built on main before 0.7.0 is cut, and refused by 0.6.0. A release from a
development version releases the version it names, and leaves main the development of the
one after. A patch release from it fixes the last release (0.6.0 -> 0.6.1), and leaves main
the development it was.
"""

import functools
import re
from dataclasses import dataclass
from typing import Literal

BumpLevel = Literal["major", "minor", "patch"]

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:\.dev(\d+))?$")

#: `[project] version = "..."` in pyproject.toml. Anchored to the line so that a version
#: pin inside a dependency specifier cannot match.
PYPROJECT_VERSION_RE = re.compile(r'^version = "(\d+\.\d+\.\d+(?:\.dev\d+)?)"$', re.MULTILINE)


@functools.total_ordering
@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    #: The N of X.Y.Z.devN: the development of X.Y.Z, which comes before it.
    dev: int | None = None

    def __str__(self) -> str:
        release = f"{self.major}.{self.minor}.{self.patch}"
        return release if self.dev is None else f"{release}.dev{self.dev}"

    def _key(self) -> tuple:
        return (self.major, self.minor, self.patch,
                0 if self.dev is not None else 1, self.dev or 0)

    def __lt__(self, other: "Version") -> bool:
        return self._key() < other._key()

    @property
    def release(self) -> "Version":
        """The version this is, or is the development of."""
        return Version(self.major, self.minor, self.patch)

    def development_of_next(self) -> "Version":
        """What main becomes once this is released: the development of the next minor."""
        following = self.bump("minor")
        return Version(following.major, following.minor, following.patch, dev=0)

    @property
    def tag(self) -> str:
        return f"v{self}"

    @classmethod
    def parse(cls, text: str) -> "Version":
        match = VERSION_RE.match(text.strip())
        if match is None:
            raise ValueError(f"Not a major.minor.patch[.devN] version: {text!r}")
        major, minor, patch, dev = match.groups()
        return cls(int(major), int(minor), int(patch), None if dev is None else int(dev))

    def bump(self, level: BumpLevel) -> "Version":
        if level == "major":
            return Version(self.major + 1, 0, 0)
        if level == "minor":
            return Version(self.major, self.minor + 1, 0)
        if level == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ValueError(f"Unknown bump level: {level!r}")


def next_version(
    current: Version,
    level: BumpLevel | None = None,
    explicit: Version | None = None,
    last_release: Version | None = None,
) -> Version:
    """The version to release, given the current one and what the caller asked for.

    With no level and no explicit version, a 0.x series bumps the minor version. At 1.0.0
    and above there is no safe default: the caller must say which level semver calls for.

    A development version already names its release: X.Y.Z.devN releases X.Y.Z, by default
    or with the level it was the development of. `major` still jumps past it. `patch` fixes
    `last_release`, the latest release tagged, which it needs; so does an explicit version
    before X.Y.Z, which must still be after `last_release`.
    """
    if explicit is not None and explicit.dev is not None:
        raise ValueError(f"{explicit} is a development version; a release is X.Y.Z.")
    if current.dev is not None:
        return _release_development(current, level, explicit, last_release)
    if explicit is not None:
        if level is not None:
            raise ValueError("Give a bump level or an explicit version, not both.")
        if explicit <= current:
            raise ValueError(f"{explicit} is not later than the current version {current}.")
        return explicit
    if level is None:
        if current.major >= 1:
            raise ValueError(
                f"The current version is {current}; at 1.0.0 and above the bump level must be "
                "given explicitly (--major, --minor, or --patch)."
            )
        level = "minor"
    return current.bump(level)


def _release_development(
    current: Version,
    level: BumpLevel | None,
    explicit: Version | None,
    last_release: Version | None,
) -> Version:
    release = current.release
    if explicit is not None:
        if level is not None:
            raise ValueError("Give a bump level or an explicit version, not both.")
        if explicit < release and (last_release is None or explicit <= last_release):
            raise ValueError(f"{explicit} is not later than the last release "
                             f"{last_release or '(none tagged)'}.")
        return explicit
    if level == "patch" and release.patch == 0:
        if last_release is None:
            raise ValueError(f"{current} is the development of {release}; a patch release "
                             "fixes the last release, and none is tagged.")
        return last_release.bump("patch")
    implied: BumpLevel = "patch" if release.patch else "minor" if release.minor else "major"
    if level is None:
        if release.major >= 1:
            raise ValueError(
                f"The current version is {current}; at 1.0.0 and above the bump level must be "
                f"given explicitly (--{implied} releases {release})."
            )
        return release
    if level == implied:
        return release
    if level == "major":
        return Version(release.major + 1, 0, 0)
    raise ValueError(
        f"{current} is the development of {release}, a {implied} release; it cannot be "
        f"released as a {level} release. Give --version instead."
    )


def read_pyproject_version(text: str) -> Version:
    """The project version declared in the text of a pyproject.toml."""
    match = PYPROJECT_VERSION_RE.search(text)
    if match is None:
        raise ValueError("No `version = \"X.Y.Z\"` line found in pyproject.toml.")
    return Version.parse(match.group(1))


def write_pyproject_version(text: str, version: Version) -> str:
    """The text of a pyproject.toml with its project version replaced. Nothing else moves."""
    new_text, count = PYPROJECT_VERSION_RE.subn(f'version = "{version}"', text, count=1)
    if count != 1:
        raise ValueError("No `version = \"X.Y.Z\"` line found in pyproject.toml.")
    return new_text
