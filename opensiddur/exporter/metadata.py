"""Metadata a compiled book carries about its sources, whatever it is rendered into.

A book's colophon — the licences of every file it drew on, the people credited in it and the
sources it cites. ``build_colophon`` gathers
the colophon once, in one order, and each output stage only serialises it: the TeX/PDF stage
(tex/latex.py) and the electronic book (html/html.py).
"""

import re
import sys
from pathlib import Path
from typing import Literal

from lxml import etree
from pydantic import BaseModel


class LicenseRecord(BaseModel):
    """Record of the license for a given file."""
    url: str  # License URL is required
    name: str


class CreditRecord(BaseModel):
    """Record of the credit for a given file."""
    role: str  # Role is required (e.g., "aut", "edt")
    resp_text: str
    ref: str  # Reference URI is required
    name_text: str
    namespace: str  # where the contributor did their work
    contributor: str  # contributor name at the source


def extract_licenses(
    xml_file_paths: list[Path],
    project_directory: Path,
) -> dict[Path, LicenseRecord]:
    """Extract license URLs and names from a list of JLPTEI XML files."""
    project_directory = project_directory.resolve()
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}

    results: dict[Path, LicenseRecord] = {}

    for file_path in xml_file_paths:
        try:
            try:
                relative_path = file_path.absolute().relative_to(project_directory)
            except ValueError:
                print(
                    f"Warning: {file_path} is not a subdirectory of {project_directory}",
                    file=sys.stderr,
                )
                continue
            tree = etree.parse(file_path)
            root = tree.getroot()
            for licence in root.findall(".//tei:licence", ns):
                url = licence.attrib.get("target")
                name = (licence.text or "").strip()
                if url:
                    results[relative_path] = LicenseRecord(url=url, name=name)
                else:
                    print(
                        f"Error: No license URL found for {relative_path}",
                        file=sys.stderr,
                    )
        except Exception as e:
            print(f"Error: {file_path}: {e}", file=sys.stderr)

    return results


def group_licenses(licenses: dict[Path, LicenseRecord]) -> list[LicenseRecord]:
    """Group licenses by URL (deduplicated), in a stable order.

    The files arrive in whatever order the document transcludes them, which says
    nothing about the licences; sorting keeps a rebuild of the same document from
    reshuffling its Legal section. Where two files name one URL differently, the name
    from the first file in path order is used.
    """
    by_url: dict[str, LicenseRecord] = {}
    for path in sorted(licenses):
        by_url.setdefault(licenses[path].url, licenses[path])
    # A licence a file names by its URL alone is called by its URL: an unnamed entry in a
    # list of licences says nothing.
    named = [record if record.name else record.model_copy(update={"name": record.url})
             for record in by_url.values()]
    return sorted(named, key=lambda record: (record.name.casefold(), record.url))


CONTRIBUTOR_URN = "urn:x-opensiddur:contributor:"


def _contributor_of(ref: str | None, name_text: str, file_path: Path) -> tuple[str, str]:
    """The namespace a contributor's identifier belongs to, and the identifier.

    A reference that is not a contributor URN is reported rather than guessed at. Reading
    one as a URN anyway is what printed a heading of "From " with nothing after it: the
    last colon-delimited piece of ``https://he.wikisource.org/`` is not a namespace.
    """
    if not ref:
        print(f"Warning: {file_path}: {name_text or 'a contributor'} is credited with no "
              "reference; listed without one", file=sys.stderr)
        return "", name_text
    tail = ref.removeprefix(CONTRIBUTOR_URN)
    if tail == ref or "/" not in tail:
        print(f"Warning: {file_path}: {ref!r} is not a contributor URN "
              f"({CONTRIBUTOR_URN}<namespace>/<identifier>); listed without a namespace",
              file=sys.stderr)
        return "", name_text or ref
    namespace, contributor = tail.split("/", 1)
    return namespace, contributor


def extract_credits(xml_file_paths: list[Path]) -> dict[Path, list[CreditRecord]]:
    """Extract credits (respStmt entries) from a list of JLPTEI XML files."""
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    results: dict[Path, list[CreditRecord]] = {}

    for file_path in xml_file_paths:
        credits: list[CreditRecord] = []
        try:
            tree = etree.parse(file_path)
            root = tree.getroot()
            for resp_stmt in root.findall(".//tei:respStmt", ns):
                resp = resp_stmt.find("tei:resp", ns)
                name = resp_stmt.find("tei:name", ns)

                if resp is None or name is None:
                    continue

                role = resp.attrib.get("key")
                ref = name.attrib.get("ref")
                # itertext, not .text: a name may carry markup, and .text stops at the
                # first child element.
                name_text = "".join(name.itertext()).strip()

                if not role:
                    print(f"Warning: {file_path}: a credit for {name_text or 'someone'} "
                          "has no resp/@key saying what they did; not listed",
                          file=sys.stderr)
                    continue
                # A credit with no reference is not silently dropped: a respStmt records
                # who digitised a text, and one without a reference is malformed data
                # rather than a person to leave out. It is listed under no namespace.
                namespace, contributor = _contributor_of(ref, name_text, file_path)

                credits.append(
                    CreditRecord(
                        role=role,
                        resp_text="".join(resp.itertext()).strip(),
                        ref=ref or name_text,
                        name_text=name_text,
                        namespace=namespace,
                        contributor=contributor,
                    )
                )
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
        results[file_path] = credits

    return results


def group_credits(
    credits: dict[Path, list[CreditRecord]],
) -> dict[str, dict[str, list[CreditRecord]]]:
    """Group credits by role -> namespace -> [CreditRecord], deduplicated by (role, ref)."""
    seen: set[tuple[str, str]] = set()
    grouped: dict[str, dict[str, list[CreditRecord]]] = {}
    for credit_list in credits.values():
        for credit in credit_list:
            key = (credit.role, credit.ref)
            if key in seen:
                continue
            seen.add(key)
            grouped.setdefault(credit.role, {}).setdefault(credit.namespace, []).append(credit)
    return grouped


contributor_keys_to_roles = {
    "ann": "Annotator",
    "aut": "Author",
    "edt": "Editor",
    "fac": "Facsimilist",
    "fnd": "Funder",
    "mrk": "Markup editor",
    "pfr": "Proofreader",
    "spn": "Sponsor",
    "trl": "Translator",
    "trc": "Transcriptionist",
}



def role_order(role: str) -> tuple[int, str]:
    """Roles in the order the schema lists them, then anything unrecognised."""
    keys = list(contributor_keys_to_roles)
    return (keys.index(role) if role in keys else len(keys), role)


def role_name(role: str, namespace_dict: dict[str, list[CreditRecord]]) -> str:
    """What to call this kind of contribution.

    A recognised MARC key has a name of its own. For anything else the document's own
    ``tei:resp`` wording says what the person did, and is a better heading than the raw
    three-letter code the reader would otherwise be shown.
    """
    if role in contributor_keys_to_roles:
        return contributor_keys_to_roles[role]
    said = [c.resp_text for group in namespace_dict.values() for c in group if c.resp_text]
    return said[0] if said else role


class NamespaceCredits(BaseModel):
    """The people credited in one role from one namespace, in a stable order."""
    namespace: str  # "" for credits whose reference could not be read
    credits: list[CreditRecord]


class RoleCredits(BaseModel):
    """Everyone credited in one role."""
    role: str  # the MARC key
    heading: str  # what to call them: the role's name, plural when there is more than one
    namespaces: list[NamespaceCredits]

    @property
    def names(self) -> list[str]:
        """Each credited person's name, once, in the order they are listed."""
        return list(dict.fromkeys(credit.name_text
                                  for group in self.namespaces for credit in group.credits))


def order_credits(credits: dict[str, dict[str, list[CreditRecord]]]) -> list[RoleCredits]:
    """Grouped credits, in the order a colophon lists them.

    Roles in schema order, namespaces alphabetically and people by their identifier: the file
    order they were gathered in is not meaningful, and a credits list that reshuffles between
    two builds of the same document reads as though something changed.
    """
    ordered: list[RoleCredits] = []
    for role in sorted(credits, key=role_order):
        namespace_dict = credits[role]
        people = {credit.name_text for group in namespace_dict.values() for credit in group}
        # Only a role's own name takes a plural: an unrecognised role is headed by the
        # document's wording ("Illuminated by"), which does not.
        plural = role in contributor_keys_to_roles and len(people) > 1
        ordered.append(RoleCredits(
            role=role,
            heading=role_name(role, namespace_dict) + ("s" if plural else ""),
            namespaces=[
                NamespaceCredits(namespace=namespace,
                                 credits=sorted(namespace_dict[namespace],
                                                key=lambda credit: credit.contributor))
                for namespace in sorted(namespace_dict)
            ],
        ))
    return ordered


# ── Sources ─────────────────────────────────────────────────────────────────

TEI = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


class SourceRecord(BaseModel):
    """One work a book cites, read from a ``tei:bibl`` in a project's ``index.xml``.

    The values are plain text, whitespace-normalised and unescaped: escaping them is the
    business of whatever they are written into.
    """
    key: str  # cite key, unique among the book's sources
    entry_type: Literal["book", "online", "misc"]
    title: str = ""
    subtitle: str = ""
    authors: list[str] = []
    editors: list[str] = []
    edition: str = ""
    publisher: str = ""
    # The site or body that distributes the work. Only kept when it has no publisher, for
    # whom the distributor then stands in.
    distributor: str = ""
    address: list[str] = []
    date: str = ""  # of publication: ISO-shaped, or whatever the source says
    url: str = ""
    urldate: str = ""  # when the URL was consulted
    # Identifiers other than the URL and an accession number, in document order, as
    # (type, value); the type is "" when the idno has none.
    identifiers: list[tuple[str, str]] = []
    # Remarks on the citation, an accession number among them.
    notes: list[str] = []

    def work(self) -> dict:
        """What the record cites, leaving aside its key and the remarks on it."""
        return self.model_dump(exclude={"key", "notes"})


# idno types that are ISBNs. IBSN is a misspelling found in the data.
ISBN_TYPES = ("ISBN", "IBSN")
# Date shapes biblatex parses and formats itself; anything else is printed as it is.
ISO_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
_XPATH_SPACE = re.compile(r"[ \t\r\n]+")


def _normalize(text: str) -> str:
    """XPath's normalize-space: only the four XML whitespace characters are spaces."""
    return _XPATH_SPACE.sub(" ", text).strip(" \t\r\n")


def _text(element: etree._Element) -> str:
    return _normalize(element.xpath("string()"))


def _children(bibl: etree._Element, name: str) -> list[etree._Element]:
    return bibl.findall(TEI + name)


def _first_text(bibl: etree._Element, name: str) -> str:
    return next((text for element in _children(bibl, name) if (text := _text(element))), "")


def _is_citable(bibl: etree._Element) -> bool:
    """Whether a bibl names anything to cite.

    A file's pointer back to its project's index (``tei:ptr`` and ``tei:biblScope``, see
    AGENTS.md *Project layout*) is a bibl too, and printed as a source it is an empty entry.
    """
    for child in bibl:
        if child.tag in {TEI + name for name in (
                "title", "author", "editor", "publisher", "distributor", "edition", "idno",
                "date")} and _text(child):
            return True
        if child.tag == TEI + "ref" and child.get("target") is not None:
            return True
    return False


def _date_value(date: etree._Element) -> str:
    """A date's machine-readable @when, over its display text: the text may be prose
    ("Shared on Open Siddur 2013-03-17")."""
    when = date.get("when")
    return _normalize(when) if when is not None else _text(date)


def _published(bibl: etree._Element) -> etree._Element | None:
    """The date of publication. The date of consultation belongs to the URL, not to the work,
    so it is never taken as the work's date."""
    return next((date for date in _children(bibl, "date") if date.get("type") != "accessed"),
                None)


def _entry_type(bibl: etree._Element) -> str:
    if _children(bibl, "publisher") or _children(bibl, "edition"):
        return "book"
    if (bibl.find(f"{TEI}idno[@type='url']") is not None
            or bibl.find(f"{TEI}distributor/{TEI}ref") is not None
            or bibl.find(f"{TEI}ref[@target]") is not None):
        return "online"
    return "misc"


def _url(bibl: etree._Element) -> str:
    """An explicit idno, else the target of the distributor's link, else the target of a bare
    link in the bibl."""
    candidates = ([_text(idno) for idno in bibl.findall(f"{TEI}idno[@type='url']")]
                  + [_normalize(ref.get("target"))
                     for ref in bibl.findall(f"{TEI}distributor/{TEI}ref[@target]")]
                  + [_normalize(ref.get("target")) for ref in bibl.findall(f"{TEI}ref[@target]")])
    return next((candidate for candidate in candidates if candidate), "")


def _letters_and_digits(text: str) -> str:
    return "".join(c for c in text if c.isalpha() or c.isnumeric())


def _base_key(bibl: etree._Element) -> str:
    """The bibl's author and year, reduced to letters and digits.

    A key is read up to its first comma, so a display date ("March 3, 1822") or a name with a
    brace in it would otherwise end the key early and corrupt the entry.
    """
    named = next((elements[0] for name in ("author", "editor", "publisher", "distributor")
                  if (elements := _children(bibl, name))), None)
    first_word = _text(named).split(" ")[0] if named is not None else "unknown"
    published = _published(bibl)
    year = _date_value(published) if published is not None else "nd"
    return ((_letters_and_digits(first_word) or "unknown") + _letters_and_digits(year)).lower()


def _source_records(root: etree._Element) -> list[SourceRecord]:
    """The citable bibls anywhere in a document, each with a key unique within it.

    A header may hold several bibls that share an author and a year, or have neither (a
    facsimile and a transcription with no author and no date are both "unknownnd").
    Duplicate keys make BibTeX keep only the first entry, so a key that is not unique
    within its document is qualified by the bibl's xml:id, or by its position when it has
    none.
    """
    bibls = [bibl for bibl in root.iter(TEI + "bibl") if _is_citable(bibl)]
    base_keys = [_base_key(bibl) for bibl in bibls]
    records: list[SourceRecord] = []
    for bibl, base in zip(bibls, base_keys):
        same_key = [other for other, other_base in zip(bibls, base_keys) if other_base == base]
        if len(same_key) == 1:
            key = base
        elif bibl.get(XML_ID) is not None:
            key = f"{base}-{re.sub('[^A-Za-z0-9]', '', bibl.get(XML_ID)).lower()}"
        else:
            key = f"{base}-{same_key.index(bibl) + 1}"

        title = next((_text(element) for element in _children(bibl, "title")
                      if element.get("type") in (None, "main")), "")
        subtitle = next((_text(element) for element in _children(bibl, "title")
                         if element.get("type") in ("sub", "alt-sub")), "")
        published = _published(bibl)
        accessed = bibl.find(f"{TEI}date[@type='accessed']")
        idnos = [(idno.get("type") or "", _text(idno)) for idno in _children(bibl, "idno")
                 if idno.get("type") != "url" and _text(idno)]
        notes = ([_text(note) for note in _children(bibl, "note")
                  # A note typed "encoding" documents how the project encodes the source, for
                  # whoever reads the XML. It is no part of a citation of the book.
                  if note.get("type") != "encoding" and _text(note)]
                 + [f"Accession: {value}" for kind, value in idnos if kind == "Accession"])
        records.append(SourceRecord(
            key=key,
            entry_type=_entry_type(bibl),
            title=title,
            subtitle=subtitle,
            authors=[text for author in _children(bibl, "author") if (text := _text(author))],
            editors=[text for editor in _children(bibl, "editor") if (text := _text(editor))],
            edition=_first_text(bibl, "edition"),
            publisher=_first_text(bibl, "publisher"),
            distributor=("" if _children(bibl, "publisher")
                         else _first_text(bibl, "distributor")),
            address=[text for place in _children(bibl, "pubPlace")
                     if (text := _text(place.find(TEI + "ref")
                                       if place.find(TEI + "ref") is not None else place))],
            date=_date_value(published) if published is not None else "",
            url=_url(bibl),
            urldate=_date_value(accessed) if accessed is not None else "",
            identifiers=[(kind, value) for kind, value in idnos if kind != "Accession"],
            notes=notes,
        ))
    return records


def extract_sources(xml_file_paths: list[Path]) -> list[SourceRecord]:
    """The sources cited by the projects the given files belong to, each listed once.

    Read from each project's ``index.xml``. Two projects of the same book cite it identically
    but for a note, so the same key arrives twice; the book is listed once. A different work
    that happens to share an author and a year is a source in its own right, and is given a
    key of its own — unless an earlier rename already gave this same work one.
    """
    index_files = sorted({file_path.parent / "index.xml" for file_path in xml_file_paths})
    sources: list[SourceRecord] = []
    work_by_key: dict[str, dict] = {}
    for index_xml in index_files:
        try:
            records = _source_records(etree.parse(index_xml).getroot())
        except Exception as e:
            print(f"Could not read the sources in {index_xml}: {e}", file=sys.stderr)
            continue
        for record in records:
            work = record.work()
            candidate, suffix = record.key, 1
            while candidate in work_by_key:
                if work_by_key[candidate] == work:
                    break
                suffix += 1
                candidate = f"{record.key}-{suffix}"
            else:
                work_by_key[candidate] = work
                sources.append(record.model_copy(update={"key": candidate}))
    return sources



def get_file_references(input_file: Path, project_directory: Path) -> list[Path]:
    """Get all source file references from a compiled JLPTEI XML file.

    Includes the file itself, all transcluded files, and the ``index.xml``
    of every referenced project.
    """
    project_directory = project_directory.resolve()
    ns = {
        "tei": "http://www.tei-c.org/ns/1.0",
        "p": "http://jewishliturgy.org/ns/processing",
    }
    tree = etree.parse(input_file)
    root = tree.getroot()
    elements_with_references = root.xpath(
        "(self::*|.//*) [@p:project and @p:file_name]", namespaces=ns
    )

    p_project = "{http://jewishliturgy.org/ns/processing}project"
    p_file_name = "{http://jewishliturgy.org/ns/processing}file_name"

    return list(
        set(
            [
                project_directory / element.attrib[p_project] / element.attrib[p_file_name]
                for element in elements_with_references
            ]
            + [
                project_directory / element.attrib[p_project] / "index.xml"
                for element in elements_with_references
            ]
        )
    )


class Colophon(BaseModel):
    """What a book says about itself: whose work it is, under which licences, from where."""
    licenses: list[LicenseRecord]
    credits: list[RoleCredits]
    sources: list[SourceRecord]


def build_colophon(compiled_file: Path, project_directory: Path) -> Colophon:
    """The colophon of a compiled book, for any output stage to serialise.

    Licences and sources are read from the files the book was compiled from and their
    projects' indexes. Credits are read from the compiled document itself, not from those
    files: the compiler gathers every contributing document's credits into it, so the file a
    book is made from is the file that says who made it.
    """
    file_references = get_file_references(compiled_file, project_directory)
    return Colophon(
        licenses=group_licenses(extract_licenses(file_references, project_directory)),
        credits=order_credits(group_credits(extract_credits([compiled_file]))),
        sources=extract_sources(file_references),
    )
