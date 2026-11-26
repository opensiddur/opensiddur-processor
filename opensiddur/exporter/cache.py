from pathlib import Path

from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY


class XMLCache:
    def __init__(self, base_path: Path = PROJECT_DIRECTORY):
        self.base_path = base_path
        # Keyed by where the file was read from too: the base path can change after files
        # have been read (a settings file's project directory), and the same project and
        # file name there is a different file.
        self.cache: dict[tuple[Path, str, str], etree._ElementTree] = {}

    def _path_of_file(self, project: str, file_name: str) -> Path:
        return self.base_path / project / file_name

    def parse_xml(self, project: str, file_name: str) -> etree._ElementTree | None:
        key = (Path(self.base_path), project, file_name)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        path = self._path_of_file(project, file_name)
        if not path.exists():
            raise FileNotFoundError(f"File {path} not found")
        
        parsed = etree.parse(str(path))
        # The compiler reads a section's kind-of-day declaration as its gate too (day_gates,
        # imported here: it reads conditions, which need the settings this module is under).
        from opensiddur.exporter.day_gates import gate_kind_of_day_declarations
        gate_kind_of_day_declarations(parsed.getroot())
        self.cache[key] = parsed
        return parsed
