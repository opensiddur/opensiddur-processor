"""Add addressable boundaries to a shared paragraph without changing its text."""
import re

from .milestones import marked


def split_paragraph(body, urn, boundary, *, suffix='seal'):
    """Split one paragraph into reusable prefix/suffix milestone ranges.

    Parentheses outside the ranges remain diplomatic punctuation of the caller.
    Fail on missing or ambiguous anchors rather than silently moving a boundary.
    """
    pattern = (r'(<tei:div corresp="' + re.escape(urn)
               + r'">\s*<tei:p>)(.*?)(</tei:p>)')
    matches = list(re.finditer(pattern, body, re.S))
    if len(matches) != 1:
        raise ValueError(f'Expected one paragraph in {urn}')
    match = matches[0]
    content = match[2]
    if content.count(boundary) != 1:
        raise ValueError(f'Expected one split boundary in {urn}')
    prefix, tail = content.split(boundary)
    opening, closing = '', ''
    if prefix.startswith('(') and tail.endswith(')'):
        opening, closing = '(', ')'
        prefix, tail = prefix[1:], tail[:-1]
    replacement = (match[1] + opening + marked(urn + '/opening', prefix)
                   + marked(urn + '/' + suffix, boundary + tail) + closing + match[3])
    return body[:match.start()] + replacement + body[match.end():]


def detach_division(prayer, urn, name, *, first=None, last=None):
    """Move a leaf division out of its caller's conditional scope.

    A transclusion inherits conditions at the target. Shared text must therefore
    live outside the occurrence-specific condition, even when addressed by URN.
    """
    pattern = r'<tei:div corresp="' + re.escape(urn) + r'">(?:(?!<tei:div).)*?</tei:div>'
    matches = list(re.finditer(pattern, prayer['body'], re.S))
    if len(matches) != 1:
        raise ValueError(f'Expected one leaf division for {urn}')
    match = matches[0]
    detached = dict(prayer, name=name, urn=urn, body=match[0],
                    first=prayer['first'] if first is None else first,
                    last=prayer['last'] if last is None else last)
    prayer['body'] = (prayer['body'][:match.start()] +
        f'<j:transclude type="external" target="{urn}"/>' + prayer['body'][match.end():])
    return detached
