""" Reference Database """

import argparse
import ast
import io
import hashlib
import logging
from pathlib import Path
import re
import sqlite3
import sys
import tokenize
from typing import Optional

from lxml import etree
from lxml.etree import ElementBase
from pydantic import BaseModel
from opensiddur.common.constants import PROJECT_DIRECTORY, INDEX_DB_DIRECTORY
from opensiddur.common.progress import progress

logger = logging.getLogger(__name__)

INDEX_DB_FILE = INDEX_DB_DIRECTORY / "reference.db"

def _code_version(source: str) -> str:
    """A hash of what ``source`` does: its lines, without comments, docstrings or blank lines.

    Rewording a comment does not change how anything is indexed, and must not throw away a
    database that takes minutes to rebuild. The text is hashed rather than the syntax tree,
    whose printed form changes from one Python version to the next.
    """
    lines = source.splitlines()
    dropped: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        body = getattr(node, "body", None)
        if (isinstance(body, list) and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            dropped.update(range(body[0].lineno, body[0].end_lineno + 1))
    comments: dict[int, int] = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            comments[token.start[0]] = token.start[1]
    kept = []
    for number, line in enumerate(lines, start=1):
        if number in dropped:
            continue
        line = line[:comments.get(number, len(line))].rstrip()
        if line:
            kept.append(line)
    return hashlib.sha256("\n".join(kept).encode("utf-8")).hexdigest()


#: Identifies the indexing code that built a database. A database is only valid for the code
#: that wrote it: a change to how elements are indexed, or to the tables, makes every stored
#: row suspect. Hashing this module's own code means no one has to remember to bump a number
#: (opensiddur-processor#165); comments and docstrings are left out of the hash. All of the indexing
#: logic lives in this module.
REFDB_VERSION = _code_version(Path(__file__).read_text(encoding="utf-8"))

#: Every table the database holds, dropped together when the version stamp does not match.
_TABLES = ('urn_mappings', 'element_references', 'indexed_files', 'dropped_urn_mappings',
           'refdb_meta')

#: URNs under this prefix identify a stretch of text, so they must be unique within a
#: project. Other URN types (condition, notes) are names and are meant to be shared.
TEXT_URN_PREFIX = "urn:x-opensiddur:text:"

#: URNs under this prefix name a point at which an edition may print a rubric. Unlike a
#: text URN they are meant to repeat — the same instruction is referenced wherever it
#: applies, and two projects supplying one are alternative wordings the settings choose
#: between — so they are not an error. But two *different* rubrics in one project under
#: one instruction URN are two claims on one identity, and the compiler substitutes
#: whichever won the index for both. See `_warn_on_instruction_collision`.
INSTRUCTION_URN_PREFIX = "urn:x-opensiddur:instruction:"


def file_hash(file_path: Path | str) -> str:
    """The sha256 of a file's contents, which is what decides whether it needs re-indexing.

    Not the mtime: a fresh checkout gives every file an mtime of "now", which would make a
    database restored from a cache look older than every file in it.
    """
    return hashlib.sha256(Path(file_path).read_bytes()).hexdigest()


# Which milestone units contain which others.
#
# A milestone's URN scopes from the milestone to the next milestone of the *same* unit
# (schema/JLPTEI-3.md, "URN scope"), or to the next milestone of a unit that *contains* it,
# since no division crosses the boundary of a division that contains it. A verse therefore
# ends at the next verse or at the next chapter, but a chapter does not end at the next verse.
#
# Reading divisions deliberately overlap and so are absent from each other's containment sets:
# maftir re-reads the close of the seventh aliyah, weekday aliyot subdivide the Shabbat ones,
# and triennial breaks cut across the annual ones. Each is contained only by the parsha.
#
# The two sub-verse units divide a verse and are contained by it, but never by each other: the
# accentual halves and the named parts cut the verse at different points, and a named part may
# well straddle the etnachta — the Thirteen Attributes end one word past the etnachta of Exodus
# 34:7. Neither contains the other, so neither ends the other's scope. Note also that `verse`
# does not name them among *its* containers, so a sub-verse milestone never truncates the verse
# it sits inside.
UNIT_CONTAINED_BY: dict[str, frozenset[str]] = {
    "verse": frozenset({"chapter"}),
    "half-verse": frozenset({"verse", "chapter"}),
    "verse-part": frozenset({"verse", "chapter"}),
    "chapter": frozenset(),
    "parsha": frozenset(),
    "parsha.annual": frozenset(),
    "aliyah.annual": frozenset({"parsha.annual"}),
    "aliyah.weekday": frozenset({"parsha.annual"}),
    "maftir.annual": frozenset({"parsha.annual"}),
    "aliyah.festival": frozenset(),
    "maftir.festival": frozenset(),
}

# Each year of the triennial cycle divides the same parshah differently, and consecutive years
# deliberately overlap — in Beshalach, year 1's fifth aliyah and year 2's first are the same
# verses — so every year is its own unit-space rather than all three sharing one.
UNIT_CONTAINED_BY.update({
    f"{unit}.{year}": frozenset({"parsha.annual"})
    for unit in ("aliyah.triennial", "maftir.triennial")
    for year in (1, 2, 3)
})

# Two parshiyot that are sometimes read together share a file, and the reading of the combined
# week is a division of the pair rather than of either single: the fourth aliyah of the
# combined Vayakhel-Pekudei runs through the point where Pekudei begins. So it is scoped by
# the pair and not by parsha.annual, which would cut it there.
UNIT_CONTAINED_BY.update({
    "parsha.combined": frozenset(),
    "aliyah.combined": frozenset({"parsha.combined"}),
    "aliyah.weekday.combined": frozenset({"parsha.combined"}),
    "maftir.combined": frozenset({"parsha.combined"}),
})

_TRIENNIAL_PREFIXES = ("aliyah.triennial.", "maftir.triennial.")


def containing_units(unit: str | None) -> frozenset[str] | None:
    """Which units end `unit`'s scope, or None if the unit is not one this table knows.

    Inside a pair's file a triennial unit-space names the parshah it belongs to and, where the
    division depends on how the pair fell that cycle, the variation — `aliyah.triennial.
    behar.IL3.2`. Those are open-ended, so they are matched by shape rather than listed: any
    triennial unit that names more than a cycle year belongs to a pair's file and is scoped by
    the pair, since such a division may cross from one of the two parshiyot into the other.
    """
    known = UNIT_CONTAINED_BY.get(unit)
    if known is not None or unit is None:
        return known
    if unit.startswith(_TRIENNIAL_PREFIXES):
        return frozenset({"parsha.combined"})
    return None


def milestone_terminates(element: ElementBase, following: ElementBase) -> bool:
    """Whether `following` ends the scope opened by the milestone `element`.

    Scope ends at the next milestone of the same unit, or of a unit that contains it
    (`containing_units`). When either milestone carries no `@unit`, or carries one that
    is not in the containment table, fall back to comparing the number of path components
    in the URN -- the original heuristic, kept so that unit-less documents keep working.
    """
    unit = element.get('unit')
    following_unit = following.get('unit')
    containers = containing_units(unit)

    # A milestone with no @corresp opens nothing. It may still *close* something, but
    # only its own unit: a bare milestone of the same unit is the explicit terminator
    # (see JLPTEI-3, "URN scope"), used where a division ends partway through a file
    # with no sibling after it. The exact-match rule is what keeps this from catching
    # milestones that merely happen to lack a corresp for other reasons -- notably
    # unit="edition-verse", which carries @n and never @corresp, and which under the
    # path-depth fallback below would otherwise terminate every verse it follows.
    if not following.get('corresp'):
        return following_unit is not None and following_unit == unit

    if containers is not None and containing_units(following_unit) is not None:
        return following_unit == unit or following_unit in containers

    num_dividers = element.get('corresp', '').split(':')[-1].count('/')
    following_dividers = following.get('corresp', '').split(':')[-1].count('/')
    return following_dividers <= num_dividers


def _scope_container(element: ElementBase) -> Optional[ElementBase]:
    """The element a milestone's scope cannot outrun: its outermost tei:div, or else the
    section of the text it is in (tei:body, tei:front or tei:back)."""
    ns_map = {'tei': 'http://www.tei-c.org/ns/1.0'}
    containers = (element.xpath('(ancestor::tei:div)[1]', namespaces=ns_map)
                  or element.xpath('(ancestor::tei:body|ancestor::tei:front|ancestor::tei:back)[last()]',
                                   namespaces=ns_map))
    return containers[0] if containers else None


def _last_element_after(element: ElementBase, container: ElementBase) -> ElementBase:
    """The element whose subtree and tail end ``container``'s text, seen from ``element``.

    The container's last child, unless that child holds ``element``; then that child's last
    child, and so on down. What comes back is never an ancestor of ``element``, so its
    subtree and its tail are the last of the text, and every ancestor of ``element`` is closed
    around it rather than cut into.
    """
    ancestors = set(element.iterancestors())
    node = container
    while True:
        children = [child for child in node if isinstance(child.tag, str)]
        if not children:
            return node
        node = children[-1]
        if node is element or node not in ancestors:
            return node


def find_end_of_mapping(element: ElementBase) -> tuple[str, bool]:
    """Find the end element path and tail-inclusion flag for a URN mapping.

    For milestone elements, finds the element just before the next milestone that ends
    this one's scope. When nothing ends it, the scope runs to the end of the milestone's
    outermost tei:div, or of its section of the text if it is in no division. Either way the
    scope does not leave that container, and a terminating milestone outside it does not count.
    For non-milestones, the element itself is the end.

    "Just before" is the nearest preceding sibling of the next milestone, or -- when the
    next milestone is the first element in its parent -- the nearest preceding sibling of
    the closest ancestor that has one. The end element is always the node whose *tail* is
    the last text before the next milestone, which is what `include_tail` then picks up.
    Taking the deepest preceding element instead (`preceding::*[1]`) would land inside a
    subtree and drop the text between that subtree's close and the milestone.

    Returns:
        (end_element_path, include_tail)
    """
    ns_map = {'tei': 'http://www.tei-c.org/ns/1.0'}
    include_tail = False

    is_milestone = element.tag == '{http://www.tei-c.org/ns/1.0}milestone'
    if is_milestone:
        container = _scope_container(element)
        # Corresp-less milestones are included so an explicit terminator can close a
        # scope; `milestone_terminates` decides which of them actually do.
        following_milestones = element.xpath(
            './following::tei:milestone[ancestor::tei:text]', namespaces=ns_map)
        actual_end = None
        for milestone in following_milestones:
            if container is not None and container not in milestone.iterancestors():
                break  # past the end of the container; nothing beyond it ends this scope
            if milestone_terminates(element, milestone):
                node = milestone
                while node is not None:
                    preceding = node.xpath('./preceding-sibling::*[1]')
                    if preceding:
                        actual_end = preceding[0]
                        break
                    node = node.getparent()
                include_tail = True
                break
        if actual_end is None:
            # Nothing of its unit follows, so the scope runs to the end of its container, not
            # of its own parent: the last chapter of a book runs on past its first paragraph.
            if container is not None:
                actual_end = _last_element_after(element, container)
            else:
                actual_end = element.xpath('./following-sibling::*[last()]|self::*')[-1]
            include_tail = True
        return actual_end.getroottree().getpath(actual_end), include_tail
    else:
        end_path = element.getroottree().getpath(element)
        return end_path, include_tail


class UrnMapping(BaseModel):
    project: str
    file_name: str
    urn: str
    element_path: str
    element_tag: str
    element_type: Optional[str]
    end_element_path: Optional[str] = None
    end_includes_tail: bool = False

class Reference(BaseModel):
    element_path: str
    element_tag: str
    element_type: Optional[str]
    target_start: str
    target_end: Optional[str]
    target_is_id: bool
    corresponding_urn: Optional[str]
    project: str
    file_name: str

class ReferenceDatabase:
    """Database to store references to URNs and IDs."""

    def __init__(self, database_path: str | Path = INDEX_DB_FILE):
        """Initialize the SQLite database.
        
        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = Path(database_path)
        #: The files that failed to index in this session, which makes a sync fail.
        self.errors: list[str] = []
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.database_path))
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        self._init_database()
    
    def _stored_version(self) -> str | None:
        """The REFDB_VERSION that built this database, or None if it has no stamp."""
        try:
            row = self.conn.execute(
                "SELECT value FROM refdb_meta WHERE key = 'version'").fetchone()
        except sqlite3.OperationalError:
            return None
        return row['value'] if row else None

    def _init_database(self):
        """Initialize the database schema if it doesn't exist.

        A database written by different indexing code (or by code that predates the version
        stamp) is dropped and rebuilt empty; the next sync then indexes every file again.
        This also stands in for migrations: a change to a table changes REFDB_VERSION.
        """
        cursor = self.conn.cursor()
        if self._stored_version() != REFDB_VERSION:
            for table in _TABLES:
                cursor.execute(f'DROP TABLE IF EXISTS {table}')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS urn_mappings (
                urn TEXT NOT NULL,
                project TEXT NOT NULL,
                file_name TEXT NOT NULL,
                element_path TEXT NOT NULL,
                element_tag TEXT NOT NULL,
                element_type TEXT,
                end_element_path TEXT,
                end_includes_tail BOOLEAN,
                element_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (urn, project)
            )
        ''')
        # Create index on urn alone for faster lookups without project
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_urn 
            ON urn_mappings(urn)
        ''')
        # Create index on project for faster project-based queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_project 
            ON urn_mappings(project)
        ''')

        # Create table for element_references
        # This table indicates that an element of the given tag and type 
        # at the given path in the project/file
        # references a target (via @target attribute) or a target range (@targetEnd)
        # 
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS element_references (
                element_path TEXT NOT NULL,
                element_tag TEXT NOT NULL,
                element_type TEXT,
                target_start TEXT NOT NULL,
                target_end TEXT,
                target_is_id BOOLEAN NOT NULL,
                corresponding_urn TEXT,
                project TEXT NOT NULL,
                file_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ref_target_start 
            ON element_references(target_start)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ref_target_end 
            ON element_references(target_end)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ref_project 
            ON element_references(project)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ref_corresponding_urn 
            ON element_references(corresponding_urn)
        ''')

        # One row per file that indexed successfully, with the hash of the contents it was
        # indexed from. A file can contribute no URNs and no references, so this -- not the
        # other two tables -- is what says a file has been seen.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS indexed_files (
                project TEXT NOT NULL,
                file_name TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                PRIMARY KEY (project, file_name)
            )
        ''')

        # The repeats of a text URN that were left out because another file in the project
        # already holds it. When that holder goes, the files listed here are indexed again, so
        # that an incremental sync ends where a fresh build would.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dropped_urn_mappings (
                urn TEXT NOT NULL,
                project TEXT NOT NULL,
                file_name TEXT NOT NULL,
                PRIMARY KEY (urn, project, file_name)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS refdb_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        cursor.execute(
            "INSERT OR REPLACE INTO refdb_meta (key, value) VALUES ('version', ?)",
            (REFDB_VERSION,))
        self.conn.commit()

    def get_urn_mappings(self, urn: Optional[str] = None, project: Optional[str] = None) -> list[UrnMapping]:
        """Get all URN mappings for a specific URN.
        
        Args:
            urn: The URN identifier
            project: The project/directory name

        Returns:
            List of UrnMapping objects
        """
        cursor = self.conn.cursor()
        if urn and project:
            cursor.execute('''
                SELECT * FROM urn_mappings WHERE urn = ? AND project = ?''', (urn, project))
        elif urn:
            cursor.execute('''
                SELECT * FROM urn_mappings WHERE urn = ?''', (urn,))
        elif project:
            cursor.execute('''
                SELECT * FROM urn_mappings WHERE project = ?''', (project,))
        else:
            cursor.execute('''
                SELECT * FROM urn_mappings''')
        return [
            UrnMapping(
                project=row['project'],
                file_name=row['file_name'],
                urn=row['urn'],
                element_path=row['element_path'],
                element_tag=row['element_tag'],
                element_type=row['element_type'],
                end_element_path=row['end_element_path'],
                end_includes_tail=row['end_includes_tail']
            )
            for row in cursor.fetchall()]
    
    def get_references_to(self, urn: Optional[str] = None, id: Optional[str] = None, project: Optional[str] = None, file_name: Optional[str] = None, *, element_tag: Optional[str] = None) -> list[Reference]:
        """Get a list of all references to a specific URN or ID/file combination.
        
        Args:
            urn: The URN identifier
            id: The ID identifier (with or without # prefix)
            project: The project name (for id)
            file_name: The file name (for id)
            element_tag: Optionally select only references from this element tag.
                Annotation lookup uses this to avoid materializing transclusions.
        Returns:
            List of Reference objects
        """
        cursor = self.conn.cursor()
        tag_clause = " AND element_tag = ?" if element_tag is not None else ""
        tag_values = (element_tag,) if element_tag is not None else ()
        if urn:
            # In document order, file by file: a re-indexed file's rows are new, so the order
            # they were inserted in is not the order of the text.
            cursor.execute(f'''
                SELECT * FROM element_references WHERE target_start = ?{tag_clause}
                ORDER BY project, file_name, rowid''', (urn,) + tag_values)
            by_urn = cursor.fetchall()
        else:
            by_urn = []
        if id and project and file_name:
            # Ensure ID has # prefix for query
            id_with_hash = id if id.startswith('#') else f"#{id}"
            cursor.execute(f'''
                SELECT * FROM element_references WHERE target_start = ? AND target_is_id = true AND project = ? AND file_name = ?{tag_clause}
                ORDER BY rowid''', (id_with_hash, project, file_name) + tag_values)
            by_id = cursor.fetchall()
        else:
            by_id = []

        # An element path is only unique within one file, so the key needs the file and project
        # too; otherwise same-shaped files (e.g. the first note of two notes files) collapse.
        by_both = []
        seen = set()
        for row in by_urn + by_id:
            key = (row['project'], row['file_name'], row['element_path'])
            if key in seen:
                continue
            seen.add(key)
            by_both.append(row)

        return [Reference(element_path=row['element_path'], element_tag=row['element_tag'], element_type=row['element_type'], target_start=row['target_start'], target_end=row['target_end'], target_is_id=row['target_is_id'], corresponding_urn=row['corresponding_urn'], project=row['project'], file_name=row['file_name']) for row in by_both]

    def _warn_on_instruction_collision(
        self, urn: str, project: str, file_name: str, element_path: str, element_text: str
    ) -> None:
        """Warn when one instruction URN carries two different rubrics in one project.

        An instruction URN is a name, so repetition is normal and most occurrences carry no
        text at all — they point at a rubric defined elsewhere. What is not normal is two
        occurrences whose own wording differs: the URN then has two meanings, and because
        `add_urn_mapping` keeps only the last one, the compiler substitutes the winner at
        both places. Nothing errors and the wrong words reach the page.

        Only occurrences that carry text are compared. An empty occurrence is a reference,
        not a competing definition, and says nothing about what the URN means.

        This warns rather than raises: repeating an instruction is normal, and only the
        differing wording is a problem, which a person has to judge.
        """
        if not element_text or not urn.startswith(INSTRUCTION_URN_PREFIX):
            return
        cursor = self.conn.cursor()
        previous = cursor.execute(
            'SELECT file_name, element_path, element_text FROM urn_mappings '
            'WHERE urn = ? AND project = ?',
            (urn, project),
        ).fetchone()
        if previous is None or not previous['element_text']:
            return
        if previous['element_text'] == element_text:
            return
        if (previous['file_name'], previous['element_path']) == (file_name, element_path):
            return
        logger.warning(
            "%s carries two different instructions in project %r; only one of them will be "
            "used, in both places: %s:%s says %r, %s:%s says %r",
            urn, project,
            previous['file_name'], previous['element_path'], previous['element_text'],
            file_name, element_path, element_text,
        )

    def add_urn_mapping(self, project: str, file_name: str, element: ElementBase,
                        *, commit: bool = True) -> bool:
        """Add or update a URN mapping.

        Args:
            project: The project/directory name
            file_name: The file name containing the element
            element: The element that has the URN mapping
            commit: Whether to commit now; `index_file` commits a whole file at once.

        Returns:
            False if the mapping was dropped as a repeat of a text URN already mapped
            elsewhere in the project, else True.
        """
        cursor = self.conn.cursor()
        urn = element.get('corresp')
        if not urn:
            return
        element_path = element.getroottree().getpath(element)
        end_element_path, end_includes_tail = find_end_of_mapping(element)
        element_tag = element.tag
        element_type = element.get('type')
        # Only instructions need their wording kept. A text URN's element can span a whole
        # book, and joining that text would store megabytes to answer a question nobody
        # asks of it.
        element_text = (
            re.sub(r'\s+', ' ', ''.join(element.itertext())).strip()
            if urn.startswith(INSTRUCTION_URN_PREFIX) else None
        )

        # A text URN names one stretch of text. A source may still declare the same text twice
        # -- a refrain, a passage repeated in the print -- and the copies need not even be
        # identical, so a second mapping is kept out rather than refused: the first stands,
        # and the repeat is reported. Letting it pass silently is how MAM's repeated Decalogue
        # milestones went unnoticed.
        #
        # Only text URNs are identities. A condition URN is a feature name and is meant to
        # repeat — one setting selects the ta'am elyon reading everywhere it occurs — and a
        # note URN names a kind of note shared across books, so neither is rejected here.
        # Instruction URNs get the softer check below: repetition is fine, but two
        # occurrences that word the rubric differently are still two meanings for one name.
        existing = cursor.execute(
            'SELECT file_name, element_path FROM urn_mappings WHERE urn = ? AND project = ?',
            (urn, project),
        ).fetchone() if urn.startswith(TEXT_URN_PREFIX) else None
        if existing is not None and (
            existing['file_name'] != file_name or existing['element_path'] != element_path
        ):
            logger.warning(
                "%s is mapped twice in project %r; keeping %s:%s and dropping %s:%s",
                urn, project, existing['file_name'], existing['element_path'],
                file_name, element_path,
            )
            cursor.execute(
                'INSERT OR IGNORE INTO dropped_urn_mappings (urn, project, file_name) '
                'VALUES (?, ?, ?)', (urn, project, file_name))
            if commit:
                self.conn.commit()
            return False

        self._warn_on_instruction_collision(urn, project, file_name, element_path, element_text)

        cursor.execute('''
            INSERT INTO urn_mappings (urn, project, file_name, element_path, element_tag, element_type, end_element_path, end_includes_tail, element_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(urn, project) DO UPDATE SET
                file_name = excluded.file_name,
                element_path = excluded.element_path,
                element_tag = excluded.element_tag,
                element_type = excluded.element_type,
                end_element_path = excluded.end_element_path,
                end_includes_tail = excluded.end_includes_tail,
                element_text = excluded.element_text,
                updated_at = CURRENT_TIMESTAMP
        ''', (urn, project, file_name, element_path, element_tag, element_type, end_element_path, end_includes_tail, element_text))
        if commit:
            self.conn.commit()
        return True

    def add_reference(self, project: str, file_name: str, element: ElementBase,
                      *, commit: bool = True):
        """ Add a reference to the database.
        
        Args:
            element: The element that has the reference
            commit: Whether to commit now; `index_file` commits a whole file at once.
        """
        cursor = self.conn.cursor()

        target = element.get('target')
        if not target:
            return
        element_path = element.getroottree().getpath(element)
        corresponding_urn = element.get('corresp')
        tag = element.tag
        element_type = element.get('type')
        
        for target_start in re.split(r'\s+', target):
            target_end = element.get('targetEnd', target_start)
            target_is_id = target_start.startswith('#')
            cursor.execute('''
                INSERT INTO element_references (element_path, element_tag, element_type, target_start, target_end, target_is_id, corresponding_urn, project, file_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (element_path, tag, element_type, target_start, target_end, target_is_id, corresponding_urn, project, file_name))
        if commit:
            self.conn.commit()
    
    def get_urns_by_project(self, project: str) -> list[UrnMapping]:
        """Get all URN mappings for a specific project.
        
        Args:
            project: The project name to filter by
            
        Returns:
            List of dictionaries containing urn, project, and file_name
        """
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT * FROM urn_mappings WHERE project = ?',
            (project,)
        )
        return [
            UrnMapping(
                project=row['project'],
                file_name=row['file_name'],
                urn=row['urn'],
                element_path=row['element_path'],
                element_tag=row['element_tag'],
                element_type=row['element_type'],
                end_element_path=row['end_element_path'],
                end_includes_tail=row['end_includes_tail']
            )
            for row in cursor.fetchall()
        ]
    
    def get_files_by_project(self, project: str) -> list[str]:
        """Get a list of all distinct file names in a project.
        
        Args:
            project: The project name to filter by
            
        Returns:
            List of file names (sorted alphabetically)
        """
        # A file that holds only references, or nothing at all, is still a file in the
        # project, and must be found here for sync to remove it once it is deleted.
        cursor = self.conn.cursor()
        cursor.execute(
            '''SELECT file_name FROM urn_mappings WHERE project = ?
            UNION SELECT file_name FROM element_references WHERE project = ?
            UNION SELECT file_name FROM indexed_files WHERE project = ?
            ORDER BY file_name''',
            (project, project, project)
        )
        return [row['file_name'] for row in cursor.fetchall()]
    

    def get_references_by_project(self, project: str) -> list[Reference]:
        """Get a list of all references for a specific project.
        
        Args:
            project: The project name to filter by
            
        Returns:
            List of Reference objects
        """
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT * FROM element_references WHERE project = ? ORDER BY element_path',
            (project,)
        )
        return [Reference(element_path=row['element_path'], element_tag=row['element_tag'], element_type=row['element_type'], target_start=row['target_start'], target_end=row['target_end'], target_is_id=row['target_is_id'], corresponding_urn=row['corresponding_urn'], project=row['project'], file_name=row['file_name']) for row in cursor.fetchall()]
    
    def list_projects(self) -> list[str]:
        """Get a list of all distinct projects in the database.
        
        Returns:
            List of project names (sorted alphabetically)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            '''SELECT project FROM urn_mappings
            UNION SELECT project FROM element_references
            UNION SELECT project FROM indexed_files
            ORDER BY project''')
        return [row['project'] for row in cursor.fetchall()]
    
    def index_file(self, file_path: Path | str, project: str, file_name: str) -> int:
        """Index all URNs/references from a single XML file.
        
        Args:
            file_path: Full path to the XML file to index
            project: The project name this file belongs to
            file_name: The file name (without path) for the mapping
            
        Returns:
            Number of URNs/references indexed from this file
        """
        try:
            tree = etree.parse(str(file_path))
            root = tree.getroot()
            
            # Find all elements with corresp attribute
            # Handle multiple namespaces (tei and j)
            namespaces = {
                'tei': 'http://www.tei-c.org/ns/1.0',
                'j': 'http://jewishliturgy.org/ns/jlptei/2'
            }
            
            # XPath to find all elements with corresp attribute
            elements_with_corresp = root.xpath('//*[@corresp]', namespaces=namespaces)
            
            count = 0
            for element in elements_with_corresp:
                corresp = element.get('corresp')
                if corresp and corresp.startswith('urn:x-opensiddur:'):
                    if self.add_urn_mapping(project, file_name, element, commit=False):
                        count += 1
            
            elements_with_reference = root.xpath('//*[@target]', namespaces=namespaces)

            for element in elements_with_reference:
                self.add_reference(project, file_name, element, commit=False)
                count += 1
        except Exception as e:
            # A file is indexed whole or not at all: half of it would resolve the URNs before
            # the failure and not the ones after, and the sync would still look successful.
            self.conn.rollback()
            logger.error("Error indexing %s: %s", file_path, e)
            self.errors.append(f"{file_path}: {e}")
            return 0

        # Only a file that indexed cleanly is recorded as indexed. One that failed partway
        # stays unrecorded, so the next sync retries it and reports the error again instead
        # of skipping it with whatever it managed to write.
        self.conn.execute(
            '''INSERT INTO indexed_files (project, file_name, content_hash) VALUES (?, ?, ?)
            ON CONFLICT(project, file_name) DO UPDATE SET content_hash = excluded.content_hash''',
            (project, file_name, file_hash(file_path)))
        self.conn.commit()
        return count
    
    def index_project(self, project: str, project_directory: Path = PROJECT_DIRECTORY) -> int:
        """Index all URNs/references from XML files in a project directory.
        
        Args:
            project: The project name (e.g., 'tanakh-wlc-he', 'tanakh-jps-1917-en')
            project_directory: Base directory containing project subdirectories
                              (defaults to PROJECT_DIRECTORY constant)
            
        Returns:
            Total number of URNs/references indexed
        """
        project_path = Path(project_directory) / project
        
        if not project_path.exists():
            raise ValueError(f"Project directory does not exist: {project_path}")
        
        if not project_path.is_dir():
            raise ValueError(f"Project path is not a directory: {project_path}")
        
        total_urns = 0
        xml_files = sorted(project_path.glob('*.xml'))
        
        for xml_file in xml_files:
            file_name = xml_file.name
            count = self.index_file(xml_file, project, file_name)
            total_urns += count
            print(f"Indexed {count} URNs/references from {file_name}")
        
        return total_urns
    
    def remove_file(self, file_name: str, project: str) -> int:
        """Remove all URN mappings for a specific file in a project.
        
        Args:
            file_name: The file name to remove
            project: The project name
            
        Returns:
            Number of URNs removed
        """
        cursor = self.conn.cursor()
        # The files whose copies of this file's URNs were dropped must be indexed again: with
        # this file gone, one of them holds the URN now.
        cursor.execute('''
            DELETE FROM indexed_files WHERE project = ? AND file_name IN (
                SELECT dropped.file_name FROM dropped_urn_mappings AS dropped
                JOIN urn_mappings AS held
                  ON held.urn = dropped.urn AND held.project = dropped.project
                WHERE held.project = ? AND held.file_name = ? AND dropped.file_name != ?)
        ''', (project, project, file_name, file_name))
        cursor.execute(
            'DELETE FROM dropped_urn_mappings WHERE file_name = ? AND project = ?',
            (file_name, project))
        cursor.execute(
            'DELETE FROM urn_mappings WHERE file_name = ? AND project = ?',
            (file_name, project)
        )
        deleted_count = cursor.rowcount
        
        cursor.execute(
            'DELETE FROM element_references WHERE file_name = ? AND project = ?',
            (file_name, project)
        )
        deleted_count += cursor.rowcount

        cursor.execute(
            'DELETE FROM indexed_files WHERE file_name = ? AND project = ?',
            (file_name, project)
        )
        self.conn.commit()
        return deleted_count
    
    def remove_project(self, project: str) -> int:
        """Remove all URN/references mappings for an entire project.
        
        Args:
            project: The project name to remove
            
        Returns:
            Number of URNs/references removed
        """
        cursor = self.conn.cursor()
        cursor.execute(
            'DELETE FROM urn_mappings WHERE project = ?',
            (project,)
        )
        deleted_count = cursor.rowcount

        cursor.execute(
            'DELETE FROM element_references WHERE project = ?',
            (project,)
        )
        deleted_count += cursor.rowcount

        cursor.execute('DELETE FROM indexed_files WHERE project = ?', (project,))
        cursor.execute('DELETE FROM dropped_urn_mappings WHERE project = ?', (project,))
        self.conn.commit()
        return deleted_count
    
    def indexed_hash(self, file_name: str, project: str) -> str | None:
        """The content hash a file was last indexed from, or None if it is not indexed."""
        return self._get_indexed_hash(file_name, project)

    def _get_indexed_hash(self, file_name: str, project: str) -> str | None:
        """The content hash a file was last indexed from, or None if it is not indexed."""
        row = self.conn.execute(
            'SELECT content_hash FROM indexed_files WHERE file_name = ? AND project = ?',
            (file_name, project)
        ).fetchone()
        return row['content_hash'] if row else None

    def sync_file(self, file_name: str, project: str, project_directory: Path = PROJECT_DIRECTORY) -> dict:
        """Synchronize a file with the database.
        
        Checks if the file exists and if its contents differ from those it was last indexed
        from. If they do, removes old entries and re-indexes. If it doesn't exist, removes it
        from the database. Modification times are not consulted (see `_file_hash`).
        
        Args:
            file_name: The file name (e.g., 'genesis.xml')
            project: The project name
            project_directory: Base directory containing project subdirectories
            
        Returns:
            Dictionary with 'action' (added/updated/removed/skipped) and 'references' count
        """
        project_path = Path(project_directory) / project
        file_path = project_path / file_name
        
        # Check if file exists on disk
        if not file_path.exists():
            # File doesn't exist, remove from database
            removed = self.remove_file(file_name, project)
            return {'action': 'removed', 'references': removed}
        
        indexed_hash = self._get_indexed_hash(file_name, project)

        if indexed_hash is None:
            # Not indexed yet, or its last indexing failed. Clear anything a failed attempt
            # left behind before indexing it.
            self.remove_file(file_name, project)
            count = self.index_file(file_path, project, file_name)
            return {'action': 'added', 'references': count}
        elif indexed_hash != file_hash(file_path):
            # Contents changed since last index, re-index
            self.remove_file(file_name, project)
            count = self.index_file(file_path, project, file_name)
            return {'action': 'updated', 'references': count}
        else:
            # File unchanged
            return {'action': 'skipped', 'references': 0}
    
    def sync_project(self, project: str, project_directory: Path = PROJECT_DIRECTORY) -> dict:
        """Synchronize a project with the database.
        
        Checks if project directory exists, removes orphaned files from database,
        and syncs all files in the directory.
        
        Args:
            project: The project name
            project_directory: Base directory containing project subdirectories
            
        Returns:
            Dictionary with reference counts (added, updated, removed) and file counts
            (files_added, files_updated, files_removed, skipped)
        """
        project_path = Path(project_directory) / project
        
        # Check if project directory exists
        if not project_path.exists() or not project_path.is_dir():
            # Project doesn't exist, remove from database
            removed = self.remove_project(project)
            return {'action': 'project_removed', 'references': removed, 
                   'added': 0, 'updated': 0, 'removed': removed, 'skipped': 0,
                   'files_added': 0, 'files_updated': 0, 'files_removed': 0}
        
        # Get list of XML files on disk
        disk_files = {f.name for f in project_path.glob('*.xml')}
        
        # Get list of files in database
        db_files = set(self.get_files_by_project(project))
        
        # Remove files that are in database but not on disk
        orphaned_files = db_files - disk_files
        removed_count = 0
        for file_name in orphaned_files:
            removed_count += self.remove_file(file_name, project)
        
        # Sync all files that exist on disk
        added_count = 0
        updated_count = 0
        skipped_count = 0
        files_added = 0
        files_updated = 0
        
        # A file is synced again if a later file in the pass gave up a URN it had a dropped
        # copy of (see remove_file); the second pass picks it up. A file that failed to index
        # is not retried in the same sync.
        pending = sorted(disk_files)
        failed: set[str] = set()
        for pass_number in range(2):
            for file_name in pending:
                result = self.sync_file(file_name, project, project_directory)
                if self._get_indexed_hash(file_name, project) is None:
                    failed.add(file_name)
                if result['action'] == 'added':
                    added_count += result['references']
                    files_added += 1
                elif result['action'] == 'updated':
                    updated_count += result['references']
                    files_updated += 1
                elif result['action'] == 'skipped' and pass_number == 0:
                    skipped_count += 1
            pending = [name for name in sorted(disk_files)
                       if name not in failed and self._get_indexed_hash(name, project) is None]
            if not pending:
                break

        return {
            'action': 'project_synced',
            'added': added_count,
            'updated': updated_count,
            'removed': removed_count,
            'skipped': skipped_count,
            'files_added': files_added,
            'files_updated': files_updated,
            'files_removed': len(orphaned_files),
        }
    
    def sync_projects(self, project_directory: Path = PROJECT_DIRECTORY) -> dict:
        """Synchronize all projects with the database.
        
        Checks all project directories, removes orphaned projects from database,
        and syncs all existing projects.
        
        Args:
            project_directory: Base directory containing project subdirectories
            
        Returns:
            Dictionary with overall counts and per-project results
        """
        project_dir_path = Path(project_directory)
        
        if not project_dir_path.exists():
            raise ValueError(f"Project directory does not exist: {project_dir_path}")
        
        # Get list of project directories on disk (directories only)
        disk_projects = {p.name for p in project_dir_path.iterdir() if p.is_dir()}
        
        # Get list of projects in database
        db_projects = set(self.list_projects())
        
        # Remove projects that are in database but not on disk
        orphaned_projects = db_projects - disk_projects
        total_removed = 0
        for project in orphaned_projects:
            total_removed += self.remove_project(project)
        
        # Sync all projects that exist on disk
        total_added = 0
        total_updated = 0
        total_skipped = 0
        total_files_added = 0
        total_files_updated = 0
        total_files_removed = 0
        project_results = {}
        
        for project in progress(sorted(disk_projects), "Reference database sync",
                                unit="project", logger=logger):
            result = self.sync_project(project, project_directory)
            project_results[project] = result
            total_added += result.get('added', 0)
            total_updated += result.get('updated', 0)
            total_removed += result.get('removed', 0)
            total_skipped += result.get('skipped', 0)
            total_files_added += result.get('files_added', 0)
            total_files_updated += result.get('files_updated', 0)
            total_files_removed += result.get('files_removed', 0)
        
        return {
            'action': 'projects_synced',
            'total_added': total_added,
            'total_updated': total_updated,
            'total_removed': total_removed,
            'total_skipped': total_skipped,
            'total_files_added': total_files_added,
            'total_files_updated': total_files_updated,
            'total_files_removed': total_files_removed,
            'projects': project_results,
            'orphaned_projects_removed': len(orphaned_projects)
        }
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
    
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - closes connection."""
        self.close()


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    """Synchronize the reference database with the project directory.

    Opens the default database and syncs all projects, printing a summary
    of the changes made.
    """
    parser = argparse.ArgumentParser(
        description="Synchronize the reference database with JLPTEI project files."
    )
    parser.add_argument(
        "--project-directory",
        type=Path,
        default=PROJECT_DIRECTORY,
        help="Base directory containing project subdirectories (default: <repo>/opensiddur-projects/project).",
    )
    parser.add_argument(
        "--reference-db",
        type=Path,
        default=INDEX_DB_FILE,
        help="Path to reference.db (default: <repo>/database/reference.db).",
    )
    args = parser.parse_args(argv)
    project_directory = args.project_directory.resolve()
    reference_db_path = args.reference_db.resolve()

    print(f"Synchronizing reference database: {reference_db_path}")
    print(f"Project directory: {project_directory}\n")

    with ReferenceDatabase(reference_db_path) as refdb:
        try:
            result = refdb.sync_projects(project_directory)
            
            # Print summary
            print("=" * 70)
            print("Synchronization Complete")
            print("=" * 70)
            print(f"Files added:     {result['total_files_added']}")
            print(f"Files updated:   {result['total_files_updated']}")
            print(f"Files removed:   {result['total_files_removed']}")
            print(f"Files unchanged: {result['total_skipped']}")
            print(f"Total references added:   {result['total_added']}")
            print(f"Total references updated: {result['total_updated']}")
            print(f"Total references removed: {result['total_removed']}")
            print(f"Orphaned projects removed: {result['orphaned_projects_removed']}")
            
            # Print per-project details
            if result['projects']:
                print("\nPer-Project Summary:")
                print("-" * 70)
                for project, proj_result in sorted(result['projects'].items()):
                    print(f"  {project}:")
                    print(f"    Files added: {proj_result.get('files_added', 0)}, "
                          f"updated: {proj_result.get('files_updated', 0)}, "
                          f"removed: {proj_result.get('files_removed', 0)}, "
                          f"unchanged: {proj_result.get('skipped', 0)}; "
                          f"references added: {proj_result.get('added', 0)}, "
                          f"updated: {proj_result.get('updated', 0)}, "
                          f"removed: {proj_result.get('removed', 0)}")
            
            # Print final database state
            print("\nDatabase State:")
            print("-" * 70)
            projects = refdb.list_projects()
            if projects:
                for project in projects:
                    files = refdb.get_files_by_project(project)
                    urns = refdb.get_urns_by_project(project)
                    references = refdb.get_references_by_project(project)
                    print(f"  {project}: {len(files)} files, {len(urns)} URNs, {len(references)} references")
            else:
                print("  (empty)")
            
            print()
            
        except Exception as e:
            print(f"Error during synchronization: {e}")
            raise

        if refdb.errors:
            print(f"{len(refdb.errors)} file(s) could not be indexed:")
            for error in refdb.errors:
                print(f"  {error}")
            sys.exit(1)


if __name__ == '__main__':  # pragma: no cover
    # Only the CLI turns the progress log on; under the test runner the records go nowhere.
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
