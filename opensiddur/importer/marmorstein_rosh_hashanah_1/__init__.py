"""Scan-based digitization of Heidenheim–Marmorstein's first-day mahzor (1965)."""

from pathlib import Path

from opensiddur.common.constants import OUTPUT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.importer.scan.pages import BookProfile

BOOK = 'marmorstein_rosh_hashanah_1'
IDENTIFIER = 'mahzor-lyom-rishon-shel-rosh-hashanah-day-one-jenny-marmorstein-1965'
TITLE = 'prayerbook_for_the_new_year'
PROJECTS = {'he': f'{TITLE}-heidenheim-1965-he', 'en': f'{TITLE}-marmorstein-1965-en'}
EXPANDED = 'machzor_expanded-opensiddur-he'
ROOT_URN = 'urn:x-opensiddur:text:siddur:rosh_hashanah'
EXPANDED_URN = 'urn:x-opensiddur:text:siddur:machzor_expanded'


def profile(source_root=SOURCETEXTS_ROOT, output_root=OUTPUT_DIRECTORY):
    source = Path(source_root) / BOOK
    return BookProfile(BOOK, IDENTIFIER, source, Path(output_root) / BOOK, source / 'pages.json')
