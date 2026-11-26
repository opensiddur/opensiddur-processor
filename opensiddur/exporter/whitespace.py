"""Inline separator spacing shared by print and electronic output."""
import re

XML_LANG = '{http://www.w3.org/XML/1998/namespace}lang'


def closing_punctuation(context):
    """Punctuation before which an ordinary ASCII separator is unnecessary.

    French keeps its spacing before colon, semicolon, question and exclamation
    marks. Explicit nonbreaking spaces are never removed by these helpers.
    """
    language = ''
    if context is not None:
        language = next((node.get(XML_LANG) for node in [context, *context.iterancestors()]
                         if node.get(XML_LANG)), '')
    return ',.׃' if language.lower().split('-')[0] == 'fr' else ',.;:!?׃'


def closes_omitted_insert(after, context):
    """Whether an omitted insert's separator would precede closing punctuation.

    Only the new omission junction is eligible. Source spaces before punctuation,
    spaced ellipses, and nonbreaking separators retain their documentary meaning.
    """
    return bool(after and after[0] in closing_punctuation(context)
                and not re.match(r"\.[ \t]*\.", after))


def prefix_after_omission(before, after, context):
    """Remove an ASCII separator only at a newly omitted conditional's junction."""
    if closes_omitted_insert(after, context):
        return re.sub(r"[ \t\r\n]+$", "", before)
    return before
