"""Third-day service, following image-verified printed order across swapped scans."""
from .second_day import numbered_documents, verify_numbered_readings

THIRD_DAY = 'urn:x-opensiddur:text:siddur:selichot/third_day'

def documents(source):
    yield from numbered_documents(source, 'third')

def verify_readings(source, project_directory):
    return verify_numbered_readings(source, project_directory, 'third')
