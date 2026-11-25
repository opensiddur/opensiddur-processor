"""Scan digitization of Heidenheim–Marmorstein's second-day mahzor (1965)."""
from pathlib import Path

from opensiddur.common.constants import OUTPUT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.importer.scan.pages import BookProfile

BOOK = 'marmorstein_rosh_hashanah_2'
IDENTIFIER = 'mahzor-lyom-sheni-shel-rosh-hashanah-day-two-jenny-marmorstein-1965'
SOURCE_RECORD = 'https://opensiddur.org/?p=69124'
TITLE = 'prayerbook_for_the_new_year'
# Both volumes belong to the same edition projects. Day-two files must not
# overwrite day one's index, modules, settings or acceptance evidence.
PROJECTS = {'he': f'{TITLE}-heidenheim-1965-he', 'en': f'{TITLE}-marmorstein-1965-en'}
ROOT_URN = 'urn:x-opensiddur:text:siddur:rosh_hashanah/day_two'
EXPANDED = 'machzor_expanded-opensiddur-he'


def profile(source_root=SOURCETEXTS_ROOT, output_root=OUTPUT_DIRECTORY):
    source = Path(source_root) / BOOK
    return BookProfile(BOOK, IDENTIFIER, source, Path(output_root) / BOOK, source / 'pages.json')
