"""Inventory day two and cache scan images; OCR remains unverified evidence."""
import argparse
import os
from pathlib import Path

from opensiddur.common.constants import OUTPUT_DIRECTORY, SOURCETEXTS_ROOT

# These existing operations accept an explicit BookProfile and contain no
# first-day assembly or transcription rules. Keep the download behavior shared.
from opensiddur.importer.marmorstein_rosh_hashanah_1.download import (
    download,
    regenerate,
)
from opensiddur.importer.scan.pages import fetch
from opensiddur.importer.util.internet_archive import connect, resolve_agent_model

from . import profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--output-root', type=Path, default=OUTPUT_DIRECTORY)
    parser.add_argument('--contact-email', default=os.getenv('OPENSIDDUR_CONTACT_EMAIL'))
    parser.add_argument('--agent-model', default=resolve_agent_model())
    parser.add_argument('--regenerate', action='store_true')
    parser.add_argument('--pages', nargs='*', default=[])
    args = parser.parse_args(argv)
    book = profile(args.source_root, args.output_root)
    if args.regenerate:
        result = regenerate(book)
    else:
        if not args.contact_email:
            parser.error('--contact-email or OPENSIDDUR_CONTACT_EMAIL is required')
        archive = connect(args.contact_email, model=args.agent_model)
        result = download(book, archive)
        for designation in args.pages:
            fetch(book, designation, archive=archive)
    print(f"{len(result['pages'])} scan leaves inventoried; OCR remains unverified")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
