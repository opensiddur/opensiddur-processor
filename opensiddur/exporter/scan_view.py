"""What the electronic book's scan viewer shows for a page break's link to its scan.

A page break's ``@facs`` is a link a person follows: the page of the scan on the site that
hosts it, which is often a web page around the image rather than the image itself. The
viewer (``electronic.scan_viewer``) shows the scan inside the book, so it needs something it
can display: an image, which it can zoom and pan, or a PDF, which the browser's own viewer
shows. :func:`scan_view` works that out, at build time, for the sites the importers link to;
a link it does not recognise keeps opening in a new tab.
"""

import hashlib
import re
from typing import Literal, Optional
from urllib.parse import parse_qs, quote, unquote, urlsplit

ScanKind = Literal["image", "pdf"]

#: The width of the page image Wikimedia renders from a scanned document. Thumbnails are
#: made on request and cached at the widths people ask for; 1280 is one of the common ones.
WIKIMEDIA_PAGE_WIDTH = 1280

_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".webp")
#: archive.org's page images: /download/<item>/page/n<leaf>[_<size>].jpg
_ARCHIVE_PAGE = re.compile(r"^(/download/[^/]+/page/n\d+)(?:_[a-z]+)?\.jpg$")
#: A Wikisource page of a scanned document: /wiki/Page:<file>/<page>
_WIKISOURCE_PAGE = re.compile(r"^/wiki/Page:(.+)/(\d+)$")


def scan_view(facs: str) -> Optional[tuple[ScanKind, str]]:
    """The kind of thing the viewer shows for a link to a scan, and its address; or None."""
    if facs.startswith("data:image/"):
        return "image", facs
    parts = urlsplit(facs)
    if parts.scheme not in ("http", "https"):
        return None
    host = parts.netloc.lower()
    if host == "archive.org" or host.endswith(".archive.org"):
        page = _ARCHIVE_PAGE.match(parts.path)
        if page:
            # The full-size image, not the medium one the link shows: the reader zooms in.
            return "image", f"https://archive.org{page.group(1)}.jpg"
    if host == "wikisource.org" or host.endswith(".wikisource.org"):
        page = _WIKISOURCE_PAGE.match(parts.path)
        if page:
            return "image", wikimedia_page_image(unquote(page.group(1)), int(page.group(2)))
    if host in ("hebrewbooks.org", "www.hebrewbooks.org") and \
            parts.path.lower() == "/pdfpager.aspx":
        query = parse_qs(parts.query)
        book, page = query.get("req", [""])[0], query.get("pgnum", [""])[0]
        if book.isdigit() and page.isdigit():
            # The one-page PDF the site's own pager shows.
            return "pdf", (f"https://beta.hebrewbooks.org/pagefeed/"
                           f"hebrewbooks_org_{book}_{page}.pdf")
    if parts.path.lower().endswith(_IMAGE_SUFFIXES):
        return "image", facs
    return None


def wikimedia_page_image(file_name: str, page: int, width: int = WIKIMEDIA_PAGE_WIDTH) -> str:
    """A page of a scanned document on Wikimedia Commons, rendered as an image.

    Commons files sit under the first one and two hex digits of the md5 of their name,
    spaces written as underscores.
    """
    name = file_name.replace(" ", "_")
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    quoted = quote(name)
    return (f"https://upload.wikimedia.org/wikipedia/commons/thumb/{digest[0]}/{digest[:2]}/"
            f"{quoted}/page{page}-{width}px-{quoted}.jpg")
