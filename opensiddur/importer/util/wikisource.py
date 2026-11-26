"""A policy-compliant read client for Wikisource's MediaWiki Action API.

This module knows how to read page text and contributor lists from a scan-backed
(ProofreadPage) book on any Wikisource. It holds no filesystem knowledge — callers
own their own output layout and manifests.

Why the Action API and not dumps
--------------------------------
Wikimedia's robot policy asks bulk readers to check whether dumps can serve them
before making live requests. For a single book they cannot, by a wide margin. The
ProofreadPage namespace (104) appears only in ``pages-meta-current.xml.bz2``
(~447MB for hewikisource; the ``articles`` dump is namespace 0 only and contains
none of it), and per-page contributor lists need ``stub-meta-history.xml.gz``
(~160MB). That is ~600MB transferred, refreshed monthly, to extract a few MB of
wikitext — against roughly 40 batched API requests that are always current.

Dumps become the right tool at whole-wiki scale, or when full revision *text* is
needed. Somewhere in the tens of thousands of pages the balance tips; a few
hundred or a few thousand pages is comfortably API territory.

``Special:Export`` is not an option either: it caps at 35 pages per request.

The policy's preference for the website and REST API over the Action API is
scoped to *HTML* content, which is CDN-cached. We need wikitext plus contributor
metadata, and the REST wikitext endpoint has no batching — one request per page
instead of one per fifty.

On robots.txt
-------------
``robots.txt`` on Wikimedia wikis disallows ``/w/`` for ``User-agent: *``, which
read literally would cover ``/w/api.php``. That directive governs *crawlers* —
agents that discover and traverse URLs by following links — and exists to keep
search engines out of uncached ``/w/index.php`` duplicates of the canonical
``/wiki/`` URLs. It is not read as a prohibition on API clients, which is why the
robot policy publishes explicit Action API concurrency and rate limits at all;
those limits would be meaningless if robots.txt forbade API access outright.
Fetching a known list of titles is not crawling.

Rate limits observed here (unauthenticated Action API, per the robot policy):
concurrency 1 and under 5 requests/second. :class:`RateLimiter` targets roughly
0.5 req/s, and every helper is strictly serial. Do not parallelise these calls.

References:
  https://wikitech.wikimedia.org/wiki/Robot_policy
  https://www.mediawiki.org/wiki/API:Etiquette
"""

from __future__ import annotations

import logging
import os
import random
import re
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import requests
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

USER_AGENT_TEMPLATE = (
    "OpenSiddur-Processor/1.0 (https://github.com/opensiddur/opensiddur-processor; {contact_email})"
)
CONTACT_EMAIL_ENV_VAR = "OPENSIDDUR_CONTACT_EMAIL"

# Reserved placeholder domains (RFC 2606). An address here reaches nobody, so it
# fails the User-Agent policy's requirement for a genuine means of contact.
PLACEHOLDER_EMAIL_DOMAINS = ("example.com", "example.org", "example.net")

# The ProofreadPage extension uses namespace 104 for scan-backed page transcriptions
# on every Wikisource; its local name varies ("Page", "עמוד", ...).
PROOFREAD_PAGE_NAMESPACE = 104

# titles= accepts 50 per request without the apihighlimits right (500 with it).
DEFAULT_BATCH_SIZE = 50

DEFAULT_MAXLAG = 5
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_RETRIES = 5

# ~0.5 req/s against a 5 req/s ceiling.
DEFAULT_MIN_INTERVAL = 1.3

# Backoff bases, doubled per attempt when the server sends no Retry-After.
_MAXLAG_BACKOFF_BASE = 5.0
_HTTP_BACKOFF_BASE = 2.0


class WikisourceError(RuntimeError):
    """The API reported an error, or kept reporting one past our retry budget."""


class RevisionInfo(BaseModel):
    """The latest revision of a page. ``content`` is set only when it was requested."""

    revid: int = Field(description="Latest revision id")
    timestamp: str = Field(description="ISO 8601 timestamp of the latest revision")
    user: str | None = Field(default=None, description="Author of the latest revision")
    content: str | None = Field(default=None, description="Wikitext, if requested")


class RateLimiter:
    """Paces serial requests to at most one per ``min_interval`` seconds, plus jitter.

    Holds the timestamp of the last request, so it is the one genuinely stateful
    piece here and the one thing that must not be shared across threads. The
    unauthenticated Action API allows a concurrency of 1, so there should be no
    threads to share it with.
    """

    def __init__(self, min_interval: float = DEFAULT_MIN_INTERVAL) -> None:
        self.min_interval = min_interval
        self._last: float | None = None

    def wait(self) -> None:
        now = time.monotonic()
        if self._last is not None:
            delay = self.min_interval + random.random() - (now - self._last)
            if delay > 0:
                time.sleep(delay)
                now += delay
        self._last = now


@dataclass
class Wiki:
    """Everything needed to talk to one wiki: where, over what, and how fast."""

    server: str
    session: requests.Session
    limiter: RateLimiter | None = field(default=None)

    @property
    def api_url(self) -> str:
        return f"https://{self.server}/w/api.php"


def resolve_contact_email(cli_value: str | None = None) -> str:
    """Return the contact address for the User-Agent, or explain why we cannot proceed.

    Prefers an explicit value, then ``$OPENSIDDUR_CONTACT_EMAIL``. There is
    deliberately no default: Wikimedia's User-Agent policy requires a genuine means
    of contact, and quietly sending a placeholder — or the previous maintainer's
    address — is exactly the failure this guards against.
    """
    value = (cli_value or os.environ.get(CONTACT_EMAIL_ENV_VAR) or "").strip()
    if not value:
        raise WikisourceError(
            "A contact e-mail address is required before contacting Wikimedia: their "
            "User-Agent policy asks that automated clients be reachable. Pass "
            f"--contact-email or set ${CONTACT_EMAIL_ENV_VAR}."
        )
    if "@" not in value:
        raise WikisourceError(f"Not an e-mail address: {value!r}")
    domain = value.rsplit("@", 1)[1].lower()
    if domain in PLACEHOLDER_EMAIL_DOMAINS:
        raise WikisourceError(
            f"{value!r} uses the reserved placeholder domain {domain!r}, which reaches "
            "nobody. Use an address that can actually receive mail."
        )
    return value


def build_session(contact_email: str) -> requests.Session:
    """Build a session identifying us per the User-Agent policy, requesting gzip."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT_TEMPLATE.format(contact_email=contact_email),
            "Accept-Encoding": "gzip, deflate",
        }
    )
    return session


def connect(
    server: str,
    contact_email: str,
    *,
    min_interval: float = DEFAULT_MIN_INTERVAL,
) -> Wiki:
    """Convenience constructor for a paced, correctly-identified :class:`Wiki`."""
    return Wiki(
        server=server,
        session=build_session(contact_email),
        limiter=RateLimiter(min_interval),
    )


def page_title(namespace: str, book_name: str, page_num: int | str) -> str:
    """Title of one scan page, e.g. ``עמוד:Some Book.pdf/50``."""
    return f"{namespace}:{book_name}/{page_num}"


def normalize_title(title: str) -> str:
    """Canonical form of a wiki title, for comparing and deduplicating.

    MediaWiki treats underscores and spaces as the same character in titles, so the
    same page can be written either way — the Birnbaum siddur is linked both as
    ``Philip Birnbaum - …`` and ``Philip_Birnbaum_-_…``. Without folding the two,
    a link graph double-counts pages and a download set fetches them twice.

    Deliberately does not touch capitalisation: whether the first letter is
    case-insensitive is a per-wiki setting, and guessing wrong would merge two
    genuinely distinct titles, which is worse than missing a duplicate.
    """
    return re.sub(r"\s+", " ", title.replace("_", " ")).strip()


def batched(items: Sequence[Any], size: int = DEFAULT_BATCH_SIZE) -> Iterator[list[Any]]:
    """Split ``items`` into lists of at most ``size``."""
    if size < 1:
        raise ValueError("batch size must be at least 1")
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def _backoff_seconds(response: requests.Response, attempt: int, base: float) -> float:
    """Honour Retry-After when the server sends one, else back off exponentially."""
    header = response.headers.get("Retry-After")
    if header:
        try:
            return max(0.0, float(header))
        except (TypeError, ValueError):
            logger.debug("Ignoring uninterpretable Retry-After: %r", header)
    return base * (2**attempt)


def api_get(
    wiki: Wiki,
    params: dict[str, Any],
    *,
    maxlag: int = DEFAULT_MAXLAG,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    """Perform one Action API query, retrying on lag and transient failures.

    The single place in this module that touches the network, so it owns the whole
    etiquette contract: identification, pacing, ``maxlag``, and backoff.

    Sent as POST despite being a read. A batch of 50 long titles does not fit in a
    URL — fifty Hebrew subpage titles percent-encode to well over 8KB and the server
    answers 414 — and the Action API accepts POST for read queries precisely so that
    batching is not limited by URL length. Nothing else changes: `maxlag`,
    `Retry-After` and the error envelope behave identically either way.
    """
    query = dict(params)
    query.update(format="json", formatversion=2, maxlag=maxlag)

    for attempt in range(max_retries + 1):
        if wiki.limiter is not None:
            wiki.limiter.wait()

        response = wiki.session.post(wiki.api_url, data=query, timeout=timeout)

        # Rate limiting and server-side faults are worth retrying; other 4xx are our
        # own fault and will fail identically no matter how long we wait.
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == max_retries:
                response.raise_for_status()
            delay = _backoff_seconds(response, attempt, _HTTP_BACKOFF_BASE)
            logger.warning(
                "HTTP %s from %s; retrying in %.1fs (attempt %d/%d)",
                response.status_code,
                wiki.server,
                delay,
                attempt + 1,
                max_retries,
            )
            time.sleep(delay)
            continue

        response.raise_for_status()
        payload = response.json()

        # Replication lag arrives as HTTP 200 with an error in the body, so the
        # status code alone never reveals it.
        error = payload.get("error") or {}
        if error.get("code") == "maxlag":
            if attempt == max_retries:
                raise WikisourceError(
                    f"{wiki.server} still lagging after {max_retries} retries: "
                    f"{error.get('info')}"
                )
            delay = _backoff_seconds(response, attempt, _MAXLAG_BACKOFF_BASE)
            logger.warning(
                "%s is lagging (%s); waiting %.1fs (attempt %d/%d)",
                wiki.server,
                error.get("info"),
                delay,
                attempt + 1,
                max_retries,
            )
            time.sleep(delay)
            continue
        if error:
            raise WikisourceError(f"{error.get('code')}: {error.get('info')}")

        return payload

    raise WikisourceError("Exhausted retries without a response")  # pragma: no cover


def _merge_page(into: dict[str, Any], addition: dict[str, Any]) -> None:
    """Merge a continued page fragment into the entry already collected for it."""
    for key, value in addition.items():
        if isinstance(value, list):
            into.setdefault(key, []).extend(value)
        else:
            into.setdefault(key, value)


def query_pages(
    wiki: Wiki,
    params: dict[str, Any],
    **kwargs: Any,
) -> dict[str, dict[str, Any]]:
    """Run a query to exhaustion, following continuation, keyed by page title.

    ``formatversion=2`` returns ``query.pages`` as a list carrying each title, so
    results map back to the requested titles directly rather than by page id.
    """
    collected: dict[str, dict[str, Any]] = {}
    query = dict(params)

    while True:
        payload = api_get(wiki, query, **kwargs)
        for page in payload.get("query", {}).get("pages", []):
            if page.get("missing"):
                continue
            title = page.get("title")
            if title is None:
                continue
            if title in collected:
                _merge_page(collected[title], page)
            else:
                collected[title] = dict(page)

        continuation = payload.get("continue")
        if not continuation:
            return collected
        query.update(continuation)


def list_pages_with_prefix(
    wiki: Wiki,
    prefix: str,
    *,
    namespace_id: int = 0,
    **kwargs: Any,
) -> list[str]:
    """Every page title in ``namespace_id`` starting with ``prefix``.

    Titles come back in *lexicographic* order (``/1``, ``/10``, ``/100``), so reading
    a single continuation batch numerically will appear full of holes that are not
    there. Sort numerically yourself if that is what you need.
    """
    return sorted(
        query_pages(
            wiki,
            {
                "action": "query",
                "generator": "allpages",
                "gapnamespace": namespace_id,
                "gapprefix": prefix,
                "gaplimit": "max",
            },
            **kwargs,
        )
    )


def list_book_pages(
    wiki: Wiki,
    book_name: str,
    *,
    namespace_id: int = PROOFREAD_PAGE_NAMESPACE,
    **kwargs: Any,
) -> dict[int, str]:
    """Map page number to title for every transcribed page of ``book_name``.

    Enumerating beats assuming a range: it needs no hardcoded last page and it
    reports gaps honestly, for books that are only partly transcribed.
    """
    pages = list_pages_with_prefix(
        wiki, f"{book_name}/", namespace_id=namespace_id, **kwargs
    )

    # gapprefix also matches deeper subpages; keep only direct numbered children.
    pattern = re.compile(rf"^{re.escape(book_name)}/(\d+)$")
    numbered: dict[int, str] = {}
    for title in pages:
        _, _, without_namespace = title.partition(":")
        match = pattern.match(without_namespace)
        if match:
            numbered[int(match.group(1))] = title
    return numbered


def fetch_revisions(
    wiki: Wiki,
    titles: Sequence[str],
    *,
    include_content: bool,
    batch_size: int = DEFAULT_BATCH_SIZE,
    **kwargs: Any,
) -> dict[str, RevisionInfo]:
    """Latest revision of each title, with wikitext only if ``include_content``.

    With ``include_content=False`` the server never serialises wikitext, making this
    a cheap way to ask "has anything changed?" across a whole book.
    """
    properties = ["ids", "timestamp", "user"]
    if include_content:
        properties.append("content")

    revisions: dict[str, RevisionInfo] = {}
    for batch in batched(list(titles), batch_size):
        params = {
            "action": "query",
            "prop": "revisions",
            "titles": "|".join(batch),
            "rvprop": "|".join(properties),
        }
        if include_content:
            params["rvslots"] = "main"

        for title, page in query_pages(wiki, params, **kwargs).items():
            page_revisions = page.get("revisions") or []
            if not page_revisions:
                continue
            revision = page_revisions[0]
            content = None
            if include_content:
                content = (
                    revision.get("slots", {}).get("main", {}).get("content")
                )
            revisions[title] = RevisionInfo(
                revid=revision["revid"],
                timestamp=revision["timestamp"],
                user=revision.get("user"),
                content=content,
            )
    return revisions


def fetch_contributors(
    wiki: Wiki,
    titles: Sequence[str],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    exclude: Callable[[str], bool] | None = None,
    **kwargs: Any,
) -> dict[str, list[str]]:
    """Named accounts that have edited each title, deduplicated and sorted.

    Uses ``prop=contributors``, which is batchable and returns registered accounts
    already deduplicated. Anonymous edits are reported by the API only as an
    aggregate count, so they do not appear here — credits name people who can be
    identified, which is what a TEI ``respStmt`` wants. By default bots and
    temporary accounts are left out on that same reasoning; see
    :func:`is_uncreditable`.
    """
    should_exclude = exclude if exclude is not None else is_uncreditable

    contributors: dict[str, list[str]] = {}
    for batch in batched(list(titles), batch_size):
        collected = query_pages(
            wiki,
            {
                "action": "query",
                "prop": "contributors",
                "titles": "|".join(batch),
                "pclimit": "max",
            },
            **kwargs,
        )
        for title, page in collected.items():
            names = {
                contributor["name"]
                for contributor in page.get("contributors") or []
                if contributor.get("name") and not should_exclude(contributor["name"])
            }
            contributors[title] = sorted(names)
    return contributors


def is_bot_name(name: str) -> bool:
    """Whether a username looks like a bot, and so should not be credited."""
    return name.casefold().endswith("bot")


def is_temporary_account(name: str) -> bool:
    """Whether a username is one of MediaWiki's temporary accounts.

    Under IP masking, an edit made without logging in is attributed to an
    auto-generated account named ``~2026-44995-25`` rather than to a bare address.
    The name is registered as far as ``prop=contributors`` is concerned, but it
    identifies a person no better than the IP it replaced, so it is excluded on the
    same reasoning: credits name people who can be identified.

    https://www.mediawiki.org/wiki/Trust_and_Safety_Product/Temporary_Accounts
    """
    return name.startswith("~")


def is_uncreditable(name: str) -> bool:
    """Whether a contributor name should be left out of credits."""
    return is_bot_name(name) or is_temporary_account(name)


# ---------------------------------------------------------------------------
# Labeled Section Transclusion
#
# Wikisource projects routinely keep the real text on a few mainspace pages, cut
# into named sections, and let other pages pull those sections in. The scan-backed
# page view then holds almost no text of its own — the Birnbaum siddur's scan pages
# have a median size of 109 bytes.
#
# Both the parser function and the tags are localised, so a wiki in Hebrew writes
# `{{#קטע:PAGE|LABEL}}` and `<קטע התחלה=LABEL/>` where an English one writes
# `{{#lst:PAGE|LABEL}}` and `<section begin=LABEL/>`. Matching only the English
# spellings silently finds nothing rather than failing loudly, which is how this
# was missed on the first pass.
#
# https://www.mediawiki.org/wiki/Extension:Labeled_Section_Transclusion
# ---------------------------------------------------------------------------

LST_PARSER_FUNCTIONS = ("lst", "section", "קטע")
LST_SECTION_TAGS = ("section", "קטע")
LST_BEGIN_ATTRIBUTES = ("begin", "התחלה")
LST_END_ATTRIBUTES = ("end", "סוף")

REDIRECT_PREFIXES = ("#redirect", "#הפניה")

_NOWIKI_RE = re.compile(r"<nowiki>.*?</nowiki>|<!--.*?-->", re.DOTALL | re.IGNORECASE)

_TRANSCLUSION_RE = re.compile(
    r"\{\{\s*#(?:" + "|".join(LST_PARSER_FUNCTIONS) + r")\s*:\s*([^|}]+)\|([^}]*)\}\}",
    re.IGNORECASE,
)

_SECTION_BEGIN_RE = re.compile(
    r"<\s*(?:" + "|".join(LST_SECTION_TAGS) + r")\s+"
    r"(?:" + "|".join(LST_BEGIN_ATTRIBUTES) + r")\s*=\s*"
    r'(?:"([^"]*)"|\'([^\']*)\'|([^/>]+?))\s*/?\s*>',
    re.IGNORECASE,
)

_REDIRECT_RE = re.compile(
    r"^\s*(?:" + "|".join(re.escape(p) for p in REDIRECT_PREFIXES) + r")\s*:?\s*"
    r"\[\[([^\]|]+)",
    re.IGNORECASE,
)


def _strip_uninterpreted(wikitext: str) -> str:
    """Blank out spans the parser would not act on, so we do not read markup in them."""
    return _NOWIKI_RE.sub("", wikitext)


def find_transclusions(wikitext: str) -> list[tuple[str, str]]:
    """Every ``(target title, section label)`` this wikitext pulls in, in order.

    Titles are normalised; labels are returned verbatim, since a label is an opaque
    key chosen by an editor rather than a title.
    """
    return [
        (normalize_title(target), label.strip())
        for target, label in _TRANSCLUSION_RE.findall(_strip_uninterpreted(wikitext))
    ]


def find_sections(wikitext: str) -> list[str]:
    """Every section label this wikitext defines, in order, deduplicated."""
    labels: list[str] = []
    for quoted, single, bare in _SECTION_BEGIN_RE.findall(_strip_uninterpreted(wikitext)):
        label = (quoted or single or bare).strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def is_redirect(wikitext: str) -> tuple[bool, str | None]:
    """Whether this page is a redirect, and to where.

    Roughly half the Birnbaum siddur's mainspace subpages are redirects carrying
    alternative names for a service, so this is common enough to be worth reporting
    rather than treating as an oddity.
    """
    match = _REDIRECT_RE.match(_strip_uninterpreted(wikitext))
    if match is None:
        return False, None
    return True, normalize_title(match.group(1))


def download_closure(
    wiki: Wiki,
    roots: Sequence[str],
    *,
    include: Callable[[str], bool],
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_depth: int | None = None,
    **kwargs: Any,
) -> dict[str, RevisionInfo]:
    """Fetch ``roots`` and everything they transclude, breadth-first.

    ``include`` decides whether a referenced title is followed, letting callers stop
    at a namespace boundary or outside a subtree. Titles are tracked in normalised
    form, so a reference cycle terminates — which matters, because these graphs are
    genuinely cyclic: assemblies transclude scan pages that transclude assemblies.
    """
    collected: dict[str, RevisionInfo] = {}
    seen: set[str] = set()
    frontier: list[str] = []
    for title in roots:
        normalized = normalize_title(title)
        if normalized not in seen:
            seen.add(normalized)
            frontier.append(normalized)
    depth = 0

    while frontier:
        revisions = fetch_revisions(
            wiki, frontier, include_content=True, batch_size=batch_size, **kwargs
        )
        collected.update(revisions)

        if max_depth is not None and depth >= max_depth:
            break

        next_frontier: list[str] = []
        for revision in revisions.values():
            if not revision.content:
                continue
            for target, _label in find_transclusions(revision.content):
                if target in seen or not include(target):
                    continue
                seen.add(target)
                next_frontier.append(target)

        frontier = next_frontier
        depth += 1

    return collected
