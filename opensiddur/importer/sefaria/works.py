"""The Sefaria works this importer converts (``works.yaml``), and where their files live.

Everything that differs between one Metsudah volume and the next is configuration here; the
stages themselves are the same for all of them. See ``specs/SEFARIA_IMPORT.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from opensiddur.common.constants import SOURCETEXTS_ROOT

WORKS_FILE = Path(__file__).with_name("works.yaml")
STRUCTURE_DIRECTORY = Path(__file__).with_name("structure")
LANGUAGES = ("he", "en")


@dataclass(frozen=True)
class Work:
    key: str
    title: str
    versions: dict[str, str]
    projects: dict[str, str]
    title_en: str
    title_he: str
    rite: str
    licence: str
    publisher: str
    place: str
    translator: str
    date: str

    @property
    def schema_file_title(self) -> str:
        """The title as Sefaria spells it in a schema file's name."""
        return self.title.replace(" ", "_")

    def data_directory(self, sourcetexts_root: Path | None = None) -> Path:
        return sefaria_data_directory(sourcetexts_root) / self.key

    def structure_file(self, directory: Path = STRUCTURE_DIRECTORY) -> Path:
        return directory / f"{self.key}.yaml"


def sefaria_data_directory(sourcetexts_root: Path | None = None) -> Path:
    """Sefaria exports: ``<sourcetexts-root>/sefaria``."""
    root = sourcetexts_root.resolve() if sourcetexts_root is not None else SOURCETEXTS_ROOT
    return root / "sefaria"


def load_works(path: Path = WORKS_FILE) -> dict[str, Work]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    works: dict[str, Work] = {}
    for key, entry in data.items():
        missing = [lang for lang in LANGUAGES if lang not in entry.get("versions", {})
                   or lang not in entry.get("projects", {})]
        if missing:
            raise ValueError(f"{path}: {key} has no version or project for {missing}")
        works[key] = Work(
            key=key,
            title=entry["title"],
            versions=dict(entry["versions"]),
            projects=dict(entry["projects"]),
            title_en=entry["title_en"],
            title_he=entry["title_he"],
            rite=" ".join(str(entry["rite"]).split()),
            licence=entry["licence"],
            publisher=entry["publisher"],
            place=entry.get("place", ""),
            translator=entry["translator"],
            date=str(entry["date"]),
        )
    return works


def select_works(names: list[str] | None, path: Path = WORKS_FILE) -> list[Work]:
    """The works named, or all of them; an unknown name is an error."""
    works = load_works(path)
    if not names:
        return list(works.values())
    unknown = [name for name in names if name not in works]
    if unknown:
        raise SystemExit(f"unknown work(s) {unknown}; known: {sorted(works)}")
    return [works[name] for name in names]
