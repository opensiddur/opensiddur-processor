from pathlib import Path
from typing import Optional

from opensiddur.common.constants import SOURCETEXTS_ROOT
from opensiddur.importer.util.constants import Page


def default_sourcetexts_root() -> Path:
    """Default opensiddur/sourcetexts checkout root (the sourcetexts submodule)."""
    return SOURCETEXTS_ROOT


def jps1917_data_directory(sourcetexts_root: Path | None = None) -> Path:
    """JPS 1917 raw dumps: <sourcetexts-root>/jps1917."""
    root = (
        sourcetexts_root.resolve()
        if sourcetexts_root is not None
        else default_sourcetexts_root()
    )
    return root / "jps1917"


def jps1917_text_directory(sourcetexts_root: Path | None = None) -> Path:
    """Directory of per-page .txt wikitext files."""
    return jps1917_data_directory(sourcetexts_root) / "text"


def jps1917_credits_directory(sourcetexts_root: Path | None = None) -> Path:
    """Directory of per-page contributor credit files."""
    return jps1917_data_directory(sourcetexts_root) / "credits"


def birnbaum_siddur_data_directory(sourcetexts_root: Path | None = None) -> Path:
    """Birnbaum ha-Siddur ha-Shalem raw dumps: <sourcetexts-root>/birnbaum_siddur."""
    root = (
        sourcetexts_root.resolve()
        if sourcetexts_root is not None
        else default_sourcetexts_root()
    )
    return root / "birnbaum_siddur"


def birnbaum_siddur_text_directory(sourcetexts_root: Path | None = None) -> Path:
    """Directory of per-page .txt wikitext files."""
    return birnbaum_siddur_data_directory(sourcetexts_root) / "text"


def birnbaum_siddur_credits_directory(sourcetexts_root: Path | None = None) -> Path:
    """Directory of per-page contributor credit files."""
    return birnbaum_siddur_data_directory(sourcetexts_root) / "credits"


def birnbaum_siddur_source_text_directory(sourcetexts_root: Path | None = None) -> Path:
    """Mainspace pages holding the text the scan pages transclude."""
    return birnbaum_siddur_data_directory(sourcetexts_root) / "source" / "text"


def birnbaum_siddur_source_credits_directory(sourcetexts_root: Path | None = None) -> Path:
    """Contributor credits for the mainspace source pages."""
    return birnbaum_siddur_data_directory(sourcetexts_root) / "source" / "credits"


def birnbaum_siddur_external_text_directory(sourcetexts_root: Path | None = None) -> Path:
    """Pages referenced from outside the siddur's own subtree."""
    return birnbaum_siddur_data_directory(sourcetexts_root) / "external" / "text"


def birnbaum_siddur_external_credits_directory(sourcetexts_root: Path | None = None) -> Path:
    """Contributor credits for externally referenced pages."""
    return birnbaum_siddur_data_directory(sourcetexts_root) / "external" / "credits"


def birnbaum_siddur_en_data_directory(sourcetexts_root: Path | None = None) -> Path:
    """English Wikisource scan pages for the same book: <data>/en.

    The English half of the printing lives on en.wikisource, which the Hebrew scan
    pages reach by interwiki transclusion (``{{iwpage|en}}``) rather than holding the
    text themselves. It is the same scan, so its pages are keyed by the same scan page
    number as ``text/`` — see :func:`birnbaum_siddur_ia_directory` for why that
    matters.
    """
    return birnbaum_siddur_data_directory(sourcetexts_root) / "en"


def birnbaum_siddur_en_text_directory(sourcetexts_root: Path | None = None) -> Path:
    """Directory of per-page English Wikisource wikitext files."""
    return birnbaum_siddur_en_data_directory(sourcetexts_root) / "text"


def birnbaum_siddur_en_credits_directory(sourcetexts_root: Path | None = None) -> Path:
    """Contributor credits for the English Wikisource scan pages."""
    return birnbaum_siddur_en_data_directory(sourcetexts_root) / "credits"


def birnbaum_siddur_ia_directory(sourcetexts_root: Path | None = None) -> Path:
    """Internet Archive material for the same scan: <data>/ia.

    The Internet Archive item and the Commons file Wikisource indexes are the same
    scan, which is what makes its OCR usable here at all. Its leaves are numbered from
    zero, so IA leaf ``n`` is scan page ``n + 1``; everything written under this
    directory is named by the *scan page* number so that no filename anywhere in the
    tree carries the off-by-one.
    """
    return birnbaum_siddur_data_directory(sourcetexts_root) / "ia"


def birnbaum_siddur_ia_derivatives_directory(sourcetexts_root: Path | None = None) -> Path:
    """Whole-book OCR derivatives as downloaded from the Internet Archive."""
    return birnbaum_siddur_ia_directory(sourcetexts_root) / "derivatives"


def birnbaum_siddur_ia_ocr_directory(sourcetexts_root: Path | None = None) -> Path:
    """Per-page OCR text sliced out of the whole-book derivatives."""
    return birnbaum_siddur_ia_directory(sourcetexts_root) / "ocr"


def birnbaum_siddur_ia_regions_directory(sourcetexts_root: Path | None = None) -> Path:
    """Per-page page-region segmentation (running head, body, footnote)."""
    return birnbaum_siddur_ia_directory(sourcetexts_root) / "regions"


def birnbaum_siddur_correspondence_path(sourcetexts_root: Path | None = None) -> Path:
    """The page correspondence table tying the Hebrew, English and IA layers together."""
    return birnbaum_siddur_data_directory(sourcetexts_root) / "pages.json"


def title_to_relative_path(title: str, suffix: str = ".txt") -> Path:
    """Map a wiki title to a relative path, turning subpage slashes into directories.

    Mirroring the title hierarchy keeps the wiki's own organization visible on disk
    and in diffs, which is most of the value of these pages.

    Only ``%`` is escaped, so that the mapping round-trips: everything else a wiki
    title may contain — Hebrew, spaces, parentheses, the gershayim quote in
    ``צה"ל`` — is legal in a POSIX path segment and stays readable. Note the quote
    would be a problem on Windows; these files are only ever read back through
    :func:`relative_path_to_title`, so it is a portability caveat, not a bug.
    """
    segments = [segment.replace("%", "%25") for segment in title.split("/")]
    if not segments or not all(segments):
        raise ValueError(f"Title does not map to a path: {title!r}")
    return Path(*segments[:-1], segments[-1] + suffix)


def relative_path_to_title(path: Path | str, suffix: str = ".txt") -> str:
    """Inverse of :func:`title_to_relative_path`."""
    parts = list(Path(path).parts)
    if not parts:
        raise ValueError("Empty path does not map to a title")
    if parts[-1].endswith(suffix):
        parts[-1] = parts[-1][: -len(suffix)]
    return "/".join(part.replace("%25", "%") for part in parts)


def hebcal_leyning_data_directory(sourcetexts_root: Path | None = None) -> Path:
    """hebcal leyning raw data: <sourcetexts-root>/hebcal_leyning."""
    root = (
        sourcetexts_root.resolve()
        if sourcetexts_root is not None
        else default_sourcetexts_root()
    )
    return root / "hebcal_leyning"


def miqra_al_pi_hamasorah_data_directory(sourcetexts_root: Path | None = None) -> Path:
    """Miqra al pi ha-Masorah raw dumps: <sourcetexts-root>/miqra_al_pi_hamasorah."""
    root = (
        sourcetexts_root.resolve()
        if sourcetexts_root is not None
        else default_sourcetexts_root()
    )
    return root / "miqra_al_pi_hamasorah"


def miqra_al_pi_hamasorah_plus_directory(sourcetexts_root: Path | None = None) -> Path:
    """MAM-parsed plus JSON files, one per book of the 24, from MAM-basics."""
    return miqra_al_pi_hamasorah_data_directory(sourcetexts_root) / "plus"


def feinstein_haggadah_data_directory(sourcetexts_root: Path | None = None) -> Path:
    """Open Siddur Feinstein haggadah compilation dumps: <sourcetexts-root>/feinstein_haggadah_2009."""
    root = (
        sourcetexts_root.resolve()
        if sourcetexts_root is not None
        else default_sourcetexts_root()
    )
    return root / "feinstein_haggadah_2009"


def heidenheim_haggadah_data_directory(sourcetexts_root: Path | None = None) -> Path:
    """1822 Heidenheim reference facsimile: <sourcetexts-root>/heidenheim_haggadah_1822."""
    root = (
        sourcetexts_root.resolve()
        if sourcetexts_root is not None
        else default_sourcetexts_root()
    )
    return root / "heidenheim_haggadah_1822"


def heidenheim_pdf_path(sourcetexts_root: Path | None = None) -> Path | None:
    """Return the 1822 Heidenheim facsimile PDF if present."""
    data_dir = heidenheim_haggadah_data_directory(sourcetexts_root)
    for name in ("heidenheim_1822.pdf", "Hebrewbooks_org_4909.pdf"):
        path = data_dir / name
        if path.is_file():
            return path
    pdfs = sorted(data_dir.glob("*.pdf"))
    return pdfs[0] if pdfs else None


def _read_page(directory: Path, page_number: str | int, digits: int) -> Optional[Page]:
    """Return the wikitext of a page file in `directory`, or None if absent."""
    page_num = int(page_number)
    path = directory / f"{page_num:0{digits}d}.txt"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return Page.model_validate(dict(number=page_num, content=f.read()))
    except FileNotFoundError:
        return None


def _read_credits(directory: Path, page_number: str | int, digits: int) -> Optional[list[str]]:
    """Return the contributor names in a credits file, or None if absent."""
    page_num = int(page_number)
    path = directory / f"{page_num:0{digits}d}.txt"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.read().split("\n") if line.strip()]
    except FileNotFoundError:
        return None


def get_page(page_number: str | int, sourcetexts_root: Path | None = None) -> Optional[Page]:
    """Return the wikitext of the given Page, or None if it does not exist."""
    return _read_page(jps1917_text_directory(sourcetexts_root), page_number, 4)


def get_credits(page_number: str | int, sourcetexts_root: Path | None = None) -> Optional[list[str]]:
    """Return the credits of the given Page, or None if it does not exist."""
    return _read_credits(jps1917_credits_directory(sourcetexts_root), page_number, 4)


def get_birnbaum_page(page_number: str | int, sourcetexts_root: Path | None = None) -> Optional[Page]:
    """Return the wikitext of the given Birnbaum page, or None if it does not exist."""
    return _read_page(birnbaum_siddur_text_directory(sourcetexts_root), page_number, 3)


def get_birnbaum_credits(
    page_number: str | int, sourcetexts_root: Path | None = None
) -> Optional[list[str]]:
    """Return the credits of the given Birnbaum page, or None if it does not exist."""
    return _read_credits(birnbaum_siddur_credits_directory(sourcetexts_root), page_number, 3)


def get_birnbaum_en_page(
    page_number: str | int, sourcetexts_root: Path | None = None
) -> Optional[Page]:
    """Return the English Wikisource wikitext of the given scan page, or None.

    Only about a third of the book's pages exist on en.wikisource, so None here is the
    common case rather than an error.
    """
    return _read_page(birnbaum_siddur_en_text_directory(sourcetexts_root), page_number, 3)


def get_birnbaum_en_credits(
    page_number: str | int, sourcetexts_root: Path | None = None
) -> Optional[list[str]]:
    """Return the English Wikisource credits of the given scan page, or None."""
    return _read_credits(birnbaum_siddur_en_credits_directory(sourcetexts_root), page_number, 3)


def get_birnbaum_ia_ocr(
    page_number: str | int, sourcetexts_root: Path | None = None
) -> Optional[Page]:
    """Return the Internet Archive OCR of the given scan page, or None.

    Takes a scan page number, not an IA leaf number. On a Hebrew page the OCR
    interleaves Birnbaum's real English footnotes with Hebrew misread as Latin, in
    reading order; it is a provenance record, not usable prose, until segmentation
    separates the regions.
    """
    return _read_page(birnbaum_siddur_ia_ocr_directory(sourcetexts_root), page_number, 3)


def opensiddur_org_data_directory(sourcetexts_root: Path | None = None) -> Path:
    """opensiddur.org posts from the site's GitHub export: <sourcetexts-root>/opensiddur_org."""
    root = (
        sourcetexts_root.resolve()
        if sourcetexts_root is not None
        else default_sourcetexts_root()
    )
    return root / "opensiddur_org"
