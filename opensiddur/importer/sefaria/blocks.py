"""Divide an aligned leaf into the texts it sets and the rubrics between them.

A Sefaria leaf is a stretch of the book ("Upon Arising in the Morning"), not one text: it sets
Modeh Ani, Reishit Chokhmah, the blessing over the tallit katan and a Yehi Ratzon, each
introduced by an English rubric. The book marks where each text begins, by printing its first
words in bold or by heading it (``<b>אבות</b>``, unpointed). So a leaf is read into:

- :class:`TextBlock` -- one text: an optional heading and its pairs, from one opening to the
  next. A rubric inside it, with more of the text after it, stays inside it.
- :class:`Rubric` -- a run of rubrics between texts ("After washing your hands, say:"), which
  belongs to the book's running order rather than to the text after it.
- :class:`Heading` -- a heading with no text of its own before the next.

A bold opening continues the text before it, rather than opening a new one, when the text has
only its heading so far, or when the segment before it was printed whole in bold (the two lines
of the Shema's first verse). A segment an alignment decision says opens a text (``opens``) opens
one whatever its markup.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from opensiddur.importer.sefaria.align import Pair
from opensiddur.importer.sefaria.markup import EnglishKind, HebrewKind, plain_text, wholly


#: Responses the book prints as an unpointed label beside their English ("Amein."): words the
#: congregation says inside the text, not a heading.
RESPONSES = frozenset({"אמן"})


def is_response(pair: Pair) -> bool:
    return (pair.he_kind is HebrewKind.LABEL and pair.en_kind is not EnglishKind.HEADING
            and plain_text(pair.he).strip(" .,:;") in RESPONSES)


def is_placeholder(pair: Pair) -> bool:
    """An unpointed label in parentheses inside a text: a placeholder the reader fills in
    (``(פלוני/פלונית)``, "(name)"), which is part of the text, not a heading."""
    return pair.he_kind is HebrewKind.LABEL and plain_text(pair.he).startswith("(")


def is_rubric(pair: Pair) -> bool:
    """English with no Hebrew, or an unpointed Hebrew label with an English rubric (or none)."""
    if pair.he_kind is HebrewKind.EMPTY:
        return True
    return (pair.he_kind is HebrewKind.LABEL and not is_placeholder(pair) and not is_response(pair)
            and pair.en_kind in (EnglishKind.RUBRIC, EnglishKind.EMPTY))


def is_heading(pair: Pair) -> bool:
    return (pair.he_kind is HebrewKind.LABEL and not is_placeholder(pair) and not is_response(pair)
            and not is_rubric(pair))


def is_phrase(pair: Pair) -> bool:
    return (pair.he_kind in (HebrewKind.TEXT, HebrewKind.BOLD_OPENING) or is_placeholder(pair)
            or is_response(pair))


@dataclass
class TextBlock:
    head: Pair | None = None
    pairs: list[Pair] = field(default_factory=list)

    @property
    def phrases(self) -> list[Pair]:
        return [pair for pair in self.pairs if is_phrase(pair)]

    @property
    def first_index(self) -> int:
        """The 1-based Hebrew index of the block's first phrase: its name in decision files."""
        return self.phrases[0].he_index or 0


@dataclass
class Rubric:
    pairs: list[Pair]


@dataclass
class Heading:
    pair: Pair


Item = TextBlock | Rubric | Heading


def divide(pairs: tuple[Pair, ...] | list[Pair],
           is_condition_label: Callable[[Pair], bool] | None = None,
           opens: frozenset[int] = frozenset()) -> list[Item]:
    """The leaf's texts, rubrics and headings. ``is_condition_label`` says which unpointed labels
    are conditions (``conditions.yaml`` labels: <b>לפסח</b> "On Pesach"): such a label is a rubric
    inside the text it governs, however it is printed, not a heading that opens a new text."""
    items: list[Item] = []
    block: TextBlock | None = None
    pending: list[Pair] = []
    previous_wholly_bold = False

    def flush_pending() -> None:
        if pending:
            items.append(Rubric(list(pending)))
            pending.clear()

    def close() -> None:
        nonlocal block
        if block is None:
            return
        if block.phrases:
            items.append(block)
        else:
            # A heading, and perhaps rubrics after it, with no text before the next heading.
            if block.head is not None:
                items.append(Heading(block.head))
            if block.pairs:
                items.append(Rubric(list(block.pairs)))
        block = None

    for pair in pairs:
        if is_rubric(pair) or (is_condition_label is not None and is_heading(pair)
                               and is_condition_label(pair)):
            pending.append(pair)
            previous_wholly_bold = False  # a rubric between them: the next bold opens a text
            continue
        if is_heading(pair):
            close()
            flush_pending()
            block = TextBlock(head=pair)
            previous_wholly_bold = False
            continue
        if not is_phrase(pair):  # pragma: no cover - every kind is one of the three
            raise AssertionError(pair)
        starts = block is None or (bool(block.phrases) and (
            pair.he_index in opens
            or (pair.he_kind is HebrewKind.BOLD_OPENING and not previous_wholly_bold)))
        if starts:
            close()
            flush_pending()
            block = TextBlock()
        else:
            assert block is not None
            block.pairs.extend(pending)
            pending.clear()
        assert block is not None
        block.pairs.append(pair)
        previous_wholly_bold = wholly(pair.he, {"bold", "large"})
    close()
    flush_pending()
    return items


def split_block(block: TextBlock, at: int) -> tuple[TextBlock, TextBlock]:
    """``block`` cut before its ``at``-th phrase (0-based): the text before, and a new text
    from there. Rubrics between the two go with the second, which they introduce."""
    phrases = block.phrases
    if not 0 < at < len(phrases):
        raise ValueError(f"cannot split a text of {len(phrases)} phrases before phrase {at}")
    first_of_rest = phrases[at]
    cut = block.pairs.index(first_of_rest)
    # Rubrics just before the cut introduce the second text.
    while cut > 0 and not is_phrase(block.pairs[cut - 1]):
        cut -= 1
    return TextBlock(block.head, block.pairs[:cut]), TextBlock(None, block.pairs[cut:])
