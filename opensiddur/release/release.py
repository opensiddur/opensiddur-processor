"""The release itself: bump, pin the submodules, roll the changelog, tag, push, announce.

Every step that changes something goes through `Repository.run` or `Repository.write`, and
those two are what `--dry-run` and the tests replace. Commands that only read state go
through `Repository.capture` and run even under `--dry-run`, so a dry run reports the real
versions, the real tags, and the commits the release would actually pin.
"""

import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date as date_type
from pathlib import Path

from opensiddur.release import changelog
from opensiddur.release.version import (
    BumpLevel,
    Version,
    next_version,
    read_pyproject_version,
    write_pyproject_version,
)

logger = logging.getLogger(__name__)


class ReleaseError(RuntimeError):
    """The release cannot proceed."""


@dataclass
class Submodule:
    name: str
    path: str
    url: str
    branch: str


@dataclass
class Repository:
    """A checkout the release acts on, with the write side switchable off."""

    root: Path
    dry_run: bool = False
    performed: list[list[str]] = field(default_factory=list)
    """Every mutating command, in order — what a dry run reports and the tests assert on."""

    written: dict[Path, str] = field(default_factory=dict)
    """Every file the release would write, by path."""

    def capture(self, *args: str) -> str:
        """Run a read-only command and return its stdout. Runs even under --dry-run."""
        result = subprocess.run(
            args, cwd=self.root, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise ReleaseError(
                f"{' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout.strip()

    def run(self, *args: str) -> None:
        """Run a mutating command, or, under --dry-run, only record it."""
        self.performed.append(list(args))
        if self.dry_run:
            logger.info("would run: %s", " ".join(args))
            return
        logger.info("running: %s", " ".join(args))
        result = subprocess.run(args, cwd=self.root, check=False)
        if result.returncode != 0:
            raise ReleaseError(f"{' '.join(args)} failed ({result.returncode}).")

    def read(self, relative: str) -> str:
        return (self.root / relative).read_text(encoding="utf-8")

    def write(self, relative: str, text: str) -> None:
        """Write a file, or, under --dry-run, only record what would be written."""
        path = self.root / relative
        self.written[path] = text
        if self.dry_run:
            logger.info("would write: %s (%d bytes)", relative, len(text))
            return
        logger.info("writing: %s", relative)
        path.write_text(text, encoding="utf-8")

    # --- read-only queries -------------------------------------------------

    def current_branch(self) -> str:
        return self.capture("git", "rev-parse", "--abbrev-ref", "HEAD")

    def submodules(self) -> list[Submodule]:
        """The submodules declared in .gitmodules, each with the branch it tracks."""
        raw = self.capture(
            "git", "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*"
        )
        values: dict[str, dict[str, str]] = {}
        for line in raw.splitlines():
            key, _, value = line.partition(" ")
            _, name, attribute = key.split(".", 2)
            values.setdefault(name, {})[attribute] = value
        modules = []
        for name, attributes in sorted(values.items()):
            if "branch" not in attributes:
                raise ReleaseError(
                    f"Submodule {name!r} declares no branch in .gitmodules, so the release "
                    "cannot tell which branch to pin it from."
                )
            modules.append(
                Submodule(
                    name=name,
                    path=attributes["path"],
                    url=attributes["url"],
                    branch=attributes["branch"],
                )
            )
        return modules

    def last_release(self) -> Version | None:
        """The latest release tagged here, vX.Y.Z; None before the first."""
        for tag in self.capture("git", "tag", "--list", "v*", "--sort=-v:refname").splitlines():
            try:
                found = Version.parse(tag.removeprefix("v"))
            except ValueError:
                continue
            if found.dev is None:
                return found
        return None

    def tag_exists(self, tag: str) -> bool:
        if self.capture("git", "tag", "--list", tag):
            return True
        return bool(self.capture("git", "ls-remote", "--tags", "origin", tag))

    def remote_head(self, submodule: Submodule) -> str:
        """The commit at the tip of the branch a submodule tracks, read from its remote."""
        raw = self.capture(
            "git", "ls-remote", submodule.url, f"refs/heads/{submodule.branch}"
        )
        if not raw:
            raise ReleaseError(
                f"{submodule.url} has no branch {submodule.branch!r} to pin {submodule.path} from."
            )
        return raw.split()[0]

    def submodule_head(self, submodule: Submodule) -> str:
        return self.capture("git", "-C", submodule.path, "rev-parse", "HEAD")


@dataclass
class ReleasePlan:
    current: Version
    version: Version
    pinned: dict[str, str]
    notes: str


def update_submodules(repo: Repository) -> dict[str, str]:
    """Move every submodule to the tip of the branch it tracks; return the pinned commits.

    Under a dry run nothing moves, so the commits are read from the remotes instead — the
    same commits the real run would land on, barring a push in between.
    """
    submodules = repo.submodules()
    if not submodules:
        raise ReleaseError("No submodules are declared; there is nothing to pin.")
    repo.run("git", "submodule", "update", "--init", "--remote")
    return {
        module.path: (
            repo.remote_head(module) if repo.dry_run else repo.submodule_head(module)
        )
        for module in submodules
    }


def release(
    repo: Repository,
    level: BumpLevel | None = None,
    explicit: Version | None = None,
    today: date_type | None = None,
    publish: bool = True,
) -> ReleasePlan:
    """Cut a release from the checkout `repo` points at, and return what it did."""
    current = read_pyproject_version(repo.read("pyproject.toml"))
    version = next_version(current, level=level, explicit=explicit,
                           last_release=repo.last_release())
    if repo.tag_exists(version.tag):
        raise ReleaseError(f"{version.tag} already exists locally or on origin.")

    pinned = update_submodules(repo)

    repo.write(
        "pyproject.toml", write_pyproject_version(repo.read("pyproject.toml"), version)
    )
    rolled = changelog.roll(
        repo.read("CHANGELOG.md"),
        version,
        (today or date_type.today()).isoformat(),
        pinned=pinned,
    )
    repo.write("CHANGELOG.md", rolled.text)

    branch = repo.current_branch()
    repo.run("git", "add", "pyproject.toml", "CHANGELOG.md", *sorted(pinned))
    repo.run("git", "commit", "-m", f"Release {version.tag}")
    with _notes_file(repo, version, rolled.notes) as notes_path:
        repo.run("git", "tag", "-a", version.tag, "-F", str(notes_path))
        if current.dev is not None:
            # Main goes on as the development of the next release, so that a settings file
            # can require what main has (`requires_processor`) before it is released. A patch
            # release of the last one leaves it the development it was.
            following = (version.development_of_next() if version >= current.release
                         else current)
            repo.write("pyproject.toml",
                       write_pyproject_version(repo.read("pyproject.toml"), following))
            repo.run("git", "add", "pyproject.toml")
            repo.run("git", "commit", "-m", f"Begin {following}")
        repo.run("git", "push", "origin", branch)
        repo.run("git", "push", "origin", version.tag)
        if publish:
            repo.run(
                "gh", "release", "create", version.tag,
                "--title", version.tag,
                "--notes-file", str(notes_path),
            )

    return ReleasePlan(current=current, version=version, pinned=pinned, notes=rolled.notes)


class _notes_file:
    """A temporary file holding the release notes, for `git tag -F` and `gh --notes-file`.

    Under a dry run no file is created; the printed commands name where it would have been.
    """

    def __init__(self, repo: Repository, version: Version, notes: str):
        self.repo = repo
        self.body = f"{version.tag}\n\n{notes}\n"
        self.path: Path | None = None

    def __enter__(self) -> Path:
        if self.repo.dry_run:
            return Path(tempfile.gettempdir()) / "release-notes.md"
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".md", prefix="release-notes-", delete=False
        )
        with handle:
            handle.write(self.body)
        self.path = Path(handle.name)
        return self.path

    def __exit__(self, *exc_info) -> None:
        if self.path is not None:
            self.path.unlink(missing_ok=True)
