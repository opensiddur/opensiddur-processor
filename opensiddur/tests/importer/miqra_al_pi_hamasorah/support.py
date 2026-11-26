"""Synthetic MAM-parsed plus downloads for the tests of the MAM importer and the humash.

Nothing here reads sourcetexts.
"""

import hashlib
import json
from pathlib import Path

from opensiddur.importer.miqra_al_pi_hamasorah.convert import (
    TANAKH_INDEX,
    _book_name_he,
    _flatten_books,
)

COMMIT = "0123456789abcdef0123456789abcdef01234567"

LICENSE = """----
License:

"Miqra according to the Masorah" as found in this spreadsheet was prepared by Seth (Avi) Kadish
from materials that he originally developed at Hebrew Wikisource,
with major technical assistance from Erel Segal-Halevi and Benjamin Denckla.
All of the material is available under the CC-BY-SA 4.0 license, which is found at the following link:

[CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)

Attribution:

Attribution in English and all languages other than Hebrew shall be to "Hebrew Wikisource" (or an equivalent translation) with a direct link to the following page:

[Miqra according to the Masorah](https://en.wikisource.org/wiki/User:Dovi/Miqra_according_to_the_Masorah#beginning)

----
רשיון:

"מקרא על פי המסורה" שבגליון הנתונים הזה הוכן ע"י אבי קדיש, על בסיס חומר קיים מהפרויקט שכבר הכין באתר ויקיטקסט, ובעזרת תמיכה טכנית מכרעת מאת אראל סגל-הלוי ובנימין דנקלה. כל החומר מוגש תחת הרשיון Creative Commons ייחוס-שיתוף זהה 4.0, שנמצא בקישור הבא:

[ייחוס-שיתוף זהה 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.he)

ייחוס:

הייחוס בעברית יהיה ל"ויקיטקסט" ביחד עם קישור ישיר לדף שבקישור הבא:

[מקרא על פי המסורה](https://he.wikisource.org/wiki/%D7%9E%D7%A7%D7%A8%D7%90#%D7%A8%D7%90%D7%A9)
"""


def book39(book24_name: str, chapters: dict, sub_book_name: str | None = None) -> dict:
    return {
        "book24_name": book24_name,
        "sub_book_name": sub_book_name,
        "good_ending_plus": None,
        "chapters": chapters,
    }


HEADER = {"book24_name": "ספר", "sub_book_names": None, "chapter_counts": {}}


def write_source(sourcetexts_root: Path, files: dict[str, list[dict]]) -> Path:
    """A miniature MAM-parsed plus download: MAM's licence, the given files and a manifest
    recording each file's SHA-256. Returns the download's directory."""
    data_dir = sourcetexts_root / "miqra_al_pi_hamasorah"
    (data_dir / "plus").mkdir(parents=True, exist_ok=True)
    contents = {"LICENSE.md": LICENSE.encode("utf-8")}
    for name, book39s in files.items():
        plus_file = {"header": HEADER, "book39s": book39s}
        contents[f"plus/{name}"] = (json.dumps(plus_file, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    for path, data in contents.items():
        (data_dir / path).write_bytes(data)
    entries = [{"path": path, "sha256": hashlib.sha256(data).hexdigest()} for path, data in contents.items()]
    (data_dir / "manifest.json").write_text(
        json.dumps({"repository": "bdenckla/MAM-basics", "commit": COMMIT, "plus_path": "MAM-parsed/plus",
                    "files": entries}),
        encoding="utf-8",
    )
    return data_dir


def verse(text: list, nav: list | None = None, label: list | None = None) -> list:
    return [nav or ["__"], label or [], text]


def with_other_books(files: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """The given files and one more, Z-Other-Books.json, holding a one-verse stand-in for every
    book they do not give, since a run converts all 39 books."""
    given = {_book_name_he(given_book39) for book39s in files.values() for given_book39 in book39s}
    others = [
        book39(f"ספר {book.book_name_he}", {"1": {"1": verse(["א"])}})
        for book in _flatten_books(TANAKH_INDEX)
        if book.book_name_he not in given
    ]
    return {**files, "Z-Other-Books.json": others}
