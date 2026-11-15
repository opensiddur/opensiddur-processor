"""Choose which page breaks link to the scan of their page.

A ``tei:pb`` with ``@facs`` records where a page of a scanned edition begins, and the output
stages can set a symbol there that links to the scan (``typography.markers.scan_links``). Not
every such break belongs where the compiled book uses the text. A book that prints one text
in several places -- Birnbaum prints Ashrei at Shacharit and again at Minchah -- keeps the one
text in one file, with a page break for each printing. ``@ed`` tells them apart: its first
token is the edition and any further tokens name the printing, by the ``siddur:`` path of the
unit that prints it (``ed="1949 chol/minchah/opening"``; see ``specs/SIDDUR_URN_SCHEME.md``).

:func:`mark_scan_links` marks the breaks that belong to the context the compiled tree puts
them in, with ``p:scan-link="true"``, and removes nothing. The context is read from the
transclusions around the text: the compiler wraps each transcluded text in a
``p:transclude`` whose ``@target`` names it, so the wrappers *above* a text's own wrapper say
where the book uses it. A ``tei:div/@corresp`` inside the text names only the text's own home,
not where it is being used, so it is read only above the text's wrapper too.

The rule, for the breaks of one edition directly inside one transclusion (their *group*):

1. A break with no printing token, or a group whose breaks all name the same printings, is
   marked outright. A multi-word printing with no slash (``"1949 sukkot rites"``) is compared
   whole, so it counts as one printing.
2. Otherwise the context is read nearest first: the ``siddur:`` paths of the enclosing
   transclusions and divisions, then the printing of the nearest earlier page break in an
   enclosing group. The first level at which some printing equals a context, or one is a
   path prefix of the other, chooses the printing (the closest match, then the first in
   document order).
3. Failing that, the printing sharing the longest leading path with any context is chosen.
   Its page may begin elsewhere in this context, but the scan shows the same words.
4. Failing that, every break is marked: when the context cannot tell, no link is lost. This
   is the case of a book that copies several printings' units into one file.

A marked break is then moved forward to just before the next words it precedes, so that the
symbol stands in a line of text: a page break between two paragraphs, or before a heading,
would otherwise be set in a paragraph of its own -- in a parallel text, a paragraph the other
column has no partner for. A break that no words follow, in its own column, is unmarked, as
is a break followed directly by another of its printing, or by one linking the same scan
page: the words are on the later page.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from lxml import etree

from opensiddur.exporter.constants import PROCESSING_NAMESPACE, TEI_NS

#: Set on each page break that links to its scan.
SCAN_LINK = f"{{{PROCESSING_NAMESPACE}}}scan-link"

_PB = f"{{{TEI_NS}}}pb"
_DIV = f"{{{TEI_NS}}}div"
_TRANSCLUDE = f"{{{PROCESSING_NAMESPACE}}}transclude"
#: A page break inside these records nothing about the running text.
_EXCLUDED = frozenset({f"{{{TEI_NS}}}note", f"{{{TEI_NS}}}standOff", f"{{{TEI_NS}}}teiHeader"})
_SIDDUR = "urn:x-opensiddur:text:siddur:"
_PARALLEL_ITEM = f"{{{PROCESSING_NAMESPACE}}}parallelItem"
#: Words inside these are not the running text a page break can be moved up to.
_NOT_RUNNING = _EXCLUDED | {f"{{{TEI_NS}}}head", f"{{{TEI_NS}}}label"}
#: Elements that are set as blocks: a break before one goes inside, to its first words.
_BLOCKS = frozenset(
    [f"{{{TEI_NS}}}{name}" for name in (
        "p", "div", "lg", "l", "ab", "head", "list", "item", "label", "titlePage",
        "docTitle", "titlePart", "docImprint", "docEdition", "docAuthor", "byline",
        "epigraph", "imprimatur", "front", "body", "back", "table", "row", "cell")]
    + [f"{{{PROCESSING_NAMESPACE}}}{name}" for name in (
        "parallel", "parallelItem", "transclude")])
#: Words inside these may not be set (one reading of a choice is): the break goes before.
_WRAPPERS = frozenset({f"{{{TEI_NS}}}choice"})


@dataclass(frozen=True)
class _Break:
    element: etree.ElementBase
    edition: str
    printings: frozenset[str]


def _parse(pb: etree.ElementBase) -> _Break:
    tokens = (pb.get("ed") or "").split()
    return _Break(pb, tokens[0] if tokens else "", frozenset(tokens[1:]))


def _candidates(root: etree.ElementBase) -> list[_Break]:
    found = []
    for pb in root.iter(_PB):
        if not pb.get("facs"):
            continue
        if any(ancestor.tag in _EXCLUDED for ancestor in pb.iterancestors()):
            continue
        found.append(_parse(pb))
    return found


def _group(element: etree.ElementBase) -> etree.ElementBase | None:
    """The nearest enclosing transclusion, or None for the document itself."""
    return next(element.iterancestors(_TRANSCLUDE), None)


def _siddur_path(element: etree.ElementBase) -> str | None:
    if element.tag == _TRANSCLUDE:
        urn = element.get("target") or ""
    elif element.tag == _DIV:
        urn = element.get("corresp") or ""
    else:
        return None
    if not urn.startswith(_SIDDUR):
        return None
    return urn[len(_SIDDUR):].split("#")[0].strip("/") or None


def _segments(path: str) -> list[str]:
    return path.split("/")


def _shared(printing: str, context: str) -> int:
    """How many leading path segments two paths share."""
    count = 0
    for a, b in zip(_segments(printing), _segments(context)):
        if a != b:
            break
        count += 1
    return count


def _matches(printing: str, context: str) -> bool:
    return (printing == context or printing.startswith(context + "/")
            or context.startswith(printing + "/"))


def _choose(printings: list[str], levels: Iterable[set[str]]) -> set[str] | None:
    """The printings the context chooses, or None when it cannot tell.

    `printings` is in document order; `levels` is the context, nearest first.
    """
    levels = [level for level in levels if level]
    for level in levels:
        matched = [(max(_shared(p, c) for c in level if _matches(p, c)), -i, p)
                   for i, p in enumerate(printings) if any(_matches(p, c) for c in level)]
        if matched:
            return {max(matched)[2]}
    contexts = set().union(*levels) if levels else set()
    scored = [(max((_shared(p, c) for c in contexts), default=0), -i, p)
              for i, p in enumerate(printings)]
    best = max(scored, default=None)
    if best is not None and best[0] > 0:
        return {best[2]}
    return None


def _context(group: etree.ElementBase | None,
             earlier: Iterable[_Break]) -> list[set[str]]:
    """The context of a group, nearest first: enclosing units, then an earlier break."""
    levels: list[set[str]] = []
    if group is not None:
        for ancestor in group.iterancestors():
            path = _siddur_path(ancestor)
            if path:
                levels.append({path})
    enclosing = set(group.iterancestors()) if group is not None else set()
    for brk in earlier:
        brk_group = _group(brk.element)
        if brk.printings and (brk_group is None or brk_group in enclosing):
            levels.append(set(brk.printings))
            break
    return levels


def mark_scan_links(root: etree.ElementBase) -> None:
    """Mark, in place, each page break that links to its scan where the tree uses it."""
    candidates = _candidates(root)
    position = {id(brk.element): i for i, brk in enumerate(candidates)}
    groups: dict[tuple[int, str], list[_Break]] = {}
    group_elements: dict[int, etree.ElementBase | None] = {}
    for brk in candidates:
        group = _group(brk.element)
        group_elements[id(group)] = group
        groups.setdefault((id(group), brk.edition), []).append(brk)

    for (group_id, _edition), breaks in groups.items():
        sets = {brk.printings for brk in breaks if brk.printings}
        if len(sets) <= 1:
            chosen = None
        else:
            printings = list(dict.fromkeys(p for brk in breaks for p in sorted(brk.printings)))
            first = position[id(breaks[0].element)]
            chosen = _choose(printings, _context(group_elements[group_id],
                                                 reversed(candidates[:first])))
        for brk in breaks:
            if chosen is None or not brk.printings or brk.printings & chosen:
                brk.element.set(SCAN_LINK, "true")
    columns = _Columns(root)
    # Last first: a break moved up to words that an earlier break is moved up to as well
    # then lands before it, and the two keep their order.
    for brk in reversed(candidates):
        if brk.element.get(SCAN_LINK):
            _attach(brk.element, columns)
    for brk in candidates:
        _unmark_if_empty_page(brk.element)


def _unmark_if_empty_page(pb: etree.ElementBase) -> None:
    """A page whose words begin on the next page links nothing: the next one is linked.

    Two breaks of one printing moved up to the same words, or a source's blank page, would
    otherwise set two symbols in one place for one line; so would a unit's own break and
    the break of the text it opens with, when both are the one page of the scan. Breaks
    of different printings or editions side by side are otherwise not consecutive pages,
    and each keeps its link.
    """
    following = pb.getnext()
    if not (pb.get(SCAN_LINK) and not (pb.tail or "").strip() and following is not None
            and following.tag == _PB and following.get(SCAN_LINK)):
        return
    this, that = _parse(pb), _parse(following)
    same_printing = (this.edition, this.printings) == (that.edition, that.printings)
    if same_printing or pb.get("facs") == following.get("facs"):
        del pb.attrib[SCAN_LINK]


def _in_title_page(element: etree.ElementBase) -> bool:
    return any(a.tag == f"{{{TEI_NS}}}titlePage" for a in element.iterancestors())


class _Columns:
    """The parallel items of a tree, in document order, to find the next one in a column."""

    def __init__(self, root: etree.ElementBase):
        self.items = list(root.iter(_PARALLEL_ITEM))
        self.index = {id(item): i for i, item in enumerate(self.items)}

    def following(self, item: etree.ElementBase):
        """The later items of the same column (role), in document order."""
        role = item.get("role")
        for later in self.items[self.index[id(item)] + 1:]:
            if later.get("role") == role:
                yield later


def _attach(pb: etree.ElementBase, columns: _Columns) -> None:
    """Move a marked page break to just before the next words in its column."""
    if _in_title_page(pb):
        return
    target = _next_words(pb, columns)
    if target is None:
        del pb.attrib[SCAN_LINK]
    elif not _in_line(pb, *target):
        _move(pb, *target)


def _in_line(pb: etree.ElementBase, element: etree.ElementBase, where: str) -> bool:
    """Whether the words are already in the break's own line, so it need not move.

    They are when they follow it in the same element: in its tail, a later sibling's
    tail, or the text of a later sibling that is not a block of its own (a highlight, a
    quotation; not a paragraph).
    """
    if where == "tail":
        return element is pb or element.getparent() is pb.getparent()
    return element.getparent() is pb.getparent() and element.tag not in _BLOCKS


def _next_words(pb: etree.ElementBase, columns: _Columns):
    """Where the next running words after a page break begin, in its column.

    (element, "text") is the element's text, (element, "tail") its tail; None when no
    words follow. A parallel text is cut into blocks at its alignment points, and a page
    often begins at a cut: its words are then in the column's next block.
    """
    column = next(pb.iterancestors(_PARALLEL_ITEM), None)
    found = _first_words(_positions_after(pb, column))
    if found is None and column is not None:
        for later in columns.following(column):
            found = _first_words(_positions_within(later))
            if found is not None:
                break
    return found


def _first_words(positions):
    for element, where in positions:
        if where == "text":
            if isinstance(element.tag, str) and (element.text or "").strip() \
                    and _running(element):
                return element, where
        else:
            parent = element.getparent()
            if (element.tail or "").strip() and parent is not None and _running(parent):
                return element, where
    return None


def _positions_after(node: etree.ElementBase, scope: etree.ElementBase | None):
    """Each place text can be, in document order, after a node and within `scope`."""
    current = node
    while current is not None and current is not scope:
        yield current, "tail"
        following = current.getnext()
        if following is not None:
            yield from _positions_within(following)
            current = following
        else:
            current = current.getparent()


def _positions_within(element: etree.ElementBase):
    yield element, "text"
    for child in element:
        yield from _positions_within(child)
        yield child, "tail"


def _running(element: etree.ElementBase) -> bool:
    return not any(e.tag in _NOT_RUNNING for e in (element, *element.iterancestors()))


def _remove(pb: etree.ElementBase) -> None:
    parent = pb.getparent()
    previous = pb.getprevious()
    if previous is None:
        parent.text = (parent.text or "") + (pb.tail or "")
    else:
        previous.tail = (previous.tail or "") + (pb.tail or "")
    parent.remove(pb)
    pb.tail = None


def _move(pb: etree.ElementBase, element: etree.ElementBase, where: str) -> None:
    wrapper = next((a for a in (element, *element.iterancestors()) if a.tag in _WRAPPERS),
                   None)
    _remove(pb)
    if where == "tail" and element.tag == _PB:
        # Moved up to a break moved there before it: the earlier page goes first.
        element.addprevious(pb)
    elif wrapper is not None:
        wrapper.addprevious(pb)
    elif where == "text":
        pb.tail, element.text = element.text, None
        element.insert(0, pb)
    else:
        pb.tail, element.tail = element.tail, None
        element.addnext(pb)
