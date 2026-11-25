""" Exporter settings management utilities. """

from pathlib import Path
from typing import Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator
import yaml

from opensiddur.exporter.linear import (
    AbbreviationReading,
    DeclarationFeatureValue,
    ErrorReading,
    LinearData,
    ParallelColumnOrder,
    Undefined,
    get_linear_data,
)
from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.client_settings import is_reader_supplied
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter import feature_registry
from opensiddur.exporter.derived_settings import SettingChangeTrigger, recalculate_derived_settings
from opensiddur.exporter.typography import (
    RESOLVE_FONTS,
    NonNegativeLength,
    ScanLinkPlacement,
    TypographyConfig,
)
from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.common.version import parse_requirement, processor_version, satisfies


#: Validation context key: False skips checking that the projects and files a settings file
#: names exist here — for an output stage, which reads a compiled file, not the projects.
CHECK_PROJECTS = "check_projects"


def _project_directory_from_context(info: ValidationInfo) -> Path:
    context = info.context or {}
    return Path(context.get("project_directory") or PROJECT_DIRECTORY)


def _checks_projects(info: ValidationInfo) -> bool:
    return (info.context or {}).get(CHECK_PROJECTS, True)


def _validate_project_list(
    project_list: list[str],
    project_directory: Optional[Path] = None,
) -> list[str]:
    """Validate a list of projects."""
    if project_directory is None:
        project_directory = PROJECT_DIRECTORY  # looked up at call time so tests can patch it
    for project in project_list:
        if not (project_directory / project).exists():
            raise ValueError(f"Project {project} does not exist")
    return project_list


def _validate_projects(project_list: list[str], info: ValidationInfo) -> list[str]:
    if not _checks_projects(info):
        return project_list
    return _validate_project_list(project_list, _project_directory_from_context(info))


def _apply_project_directory(
    linear_data: LinearData,
    project_directory: Path,
) -> None:
    linear_data.xml_cache.base_path = project_directory.resolve()


class Prioritizations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transclusion: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)

    @field_validator("transclusion")
    @classmethod
    def validate_transclusion(cls, v: list[str], info: ValidationInfo) -> list[str]:
        return _validate_projects(v, info)

    @field_validator("instructions")
    @classmethod
    def validate_instructions(cls, v: list[str], info: ValidationInfo) -> list[str]:
        return _validate_projects(v, info)

class ParallelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projects: list[str] = Field(default_factory=list)
    column_order: ParallelColumnOrder = ParallelColumnOrder.PRIMARY_FIRST

    @field_validator("projects")
    @classmethod
    def validate_projects(cls, v: list[str], info: ValidationInfo) -> list[str]:
        return _validate_projects(v, info)


class PrintOnceSettings(BaseModel):
    """ Annotation types printed only the first time the book reaches them.

    Each flag governs the notes whose @type has the same name. Instructions and
    citations belong to every occurrence of their text and cannot be listed.
    """
    model_config = ConfigDict(extra="forbid")

    commentary: bool = False
    editorial: bool = False

    def note_types(self) -> set[str]:
        """ The note @type values that are printed once. """
        return {note_type for note_type, once in self.model_dump().items() if once}


class BookTarget(BaseModel):
    """ The book a settings file formats: the root file it is compiled from.

    A settings file that names its book can be compiled without -p/-f, and is what the
    release builds into a book (see opensiddur.exporter.books).
    """

    model_config = ConfigDict(extra="forbid")

    project: str
    file_name: str
    title: Optional[str] = None

    @field_validator("project")
    @classmethod
    def validate_project(cls, v: str, info: ValidationInfo) -> str:
        _validate_projects([v], info)
        return v

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, v: str, info: ValidationInfo) -> str:
        project = info.data.get("project")
        # Without a project, it already failed; don't report twice.
        if project is None or not _checks_projects(info):
            return v
        if not (_project_directory_from_context(info) / project / v).is_file():
            raise ValueError(f"File {v} does not exist in project {project}")
        return v


class ReadingSettings(BaseModel):
    """Which editorial form to read, selected before transclusion flattens markup."""

    model_config = ConfigDict(extra="forbid")
    abbreviations: AbbreviationReading = AbbreviationReading.ABBREVIATED
    # An edition's misprints (tei:sic) are read corrected (tei:corr) unless a book asks for
    # the print.
    errors: ErrorReading = ErrorReading.CORRECTED


class ElectronicSettings(BaseModel):
    """How the electronic (adaptive) book starts, before its reader has chosen otherwise.

    Read only by the electronic book: a printed book has no day to follow and shows both
    columns. A reader's own choices, once made, are remembered and win.
    """

    model_config = ConfigDict(extra="forbid")
    #: How the book knows the day: `now`, from the device's clock at the reader's place; or
    #: `none`, no particular day, every passage that turns on the day shown with its rubric --
    #: for a book read ahead of its day, as a haggadah is.
    day: Literal["now", "none"] = "now"
    #: Which columns of parallel text it shows: `both`, or `primary` or `parallel` alone.
    columns: Literal["both", "primary", "parallel"] = "both"
    #: How a whole psalm is titled: `printed`, as the edition titles it; or `uniform`, one
    #: "Psalm 23" / "תהלים כג" heading per psalm, replacing the edition's own -- for a book
    #: compiled from editions that title their psalms differently.
    psalm_titles: Literal["printed", "uniform"] = "printed"
    scan_viewer: Literal["off", "full", "vertical", "horizontal"] = Field(
        default="off",
        description=(
            "off | full | vertical | horizontal — whether a link to the scan of a page "
            "(typography.markers.scan_links) opens the scan inside the book, where it can be "
            "zoomed and panned, rather than in a new tab; and how the viewer starts: over the "
            "whole screen, beside the text, or below it. The reader can change the layout, "
            "and the book remembers it. Needs a network connection to show the scan."
        ),
    )

    @field_validator("scan_viewer", mode="before")
    @classmethod
    def read_off_as_written(cls, v):
        # YAML reads a bare `off` as false.
        return "off" if v is False else v


#: `logo` names the Open Siddur Project's logo, which the exporter carries with it.
DEFAULT_LOGO = "default"

#: Characters TeX reads as markup even inside \includegraphics's file name.
TEX_UNSAFE_PATH_CHARACTERS = set("%#{}~\\$^&")
_LOGO_SUFFIXES = (".png", ".jpg", ".jpeg")


def _no_blank_lines(lines: list[str]) -> list[str]:
    if any(not line.strip() for line in lines):
        raise ValueError("a notice's lines must not be blank: to leave the notice out, use `none`")
    return lines


class DistributionNotice(BaseModel):
    """ Who distributes the book, set on the verso of the title page.

    A book with no title page has it on a page of its own at the start of the front matter.
    """

    model_config = ConfigDict(extra="forbid")
    #: `default`, the Open Siddur Project's logo; `none`, no logo; or the path to a PNG or
    #: JPEG, relative to the settings file.
    logo: str = DEFAULT_LOGO
    #: How wide the logo is set: a length, in the units the typography settings take.
    logo_width: NonNegativeLength = "1.25in"
    #: Where on its page the notice stands.
    position: Literal["top", "center", "bottom"] = "bottom"
    #: The notice, a line each. A line that is a URL is a link; `_words_` are emphasised.
    text: list[str] = Field(
        default_factory=lambda: [
            "Distributed by The Open Siddur Project",
            "https://opensiddur.org",
            "https://github.com/opensiddur",
        ]
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: list[str]) -> list[str]:
        return _no_blank_lines(v)

    @field_validator("logo")
    @classmethod
    def validate_logo(cls, v: str) -> str:
        if v in (DEFAULT_LOGO, "none"):
            return v
        if not v.lower().endswith(_LOGO_SUFFIXES):
            raise ValueError(
                f"logo {v!r} must be `default`, `none` or a {', '.join(_LOGO_SUFFIXES)} file"
            )
        if unsafe := sorted(TEX_UNSAFE_PATH_CHARACTERS.intersection(v)):
            raise ValueError(f"logo {v!r} has characters TeX cannot take in a file name: "
                             f"{' '.join(unsafe)}")
        return v


class BackNotice(BaseModel):
    """ A statement on the book's last page, after the colophon, one for each kind of book.

    Each is a list of statements, set as a bulleted list; `_words_` are emphasised.
    """

    model_config = ConfigDict(extra="forbid")
    #: For the electronic book.
    electronic: list[str] = Field(
        default_factory=lambda: [
            "We strongly advise against printing sacred texts and art containing divine "
            "names as these copies must be regarded with reverence, complicating their "
            "casual treatment and disposal.",
            _GENIZAH_STATEMENT,
        ]
    )
    #: For the printed book.
    print: list[str] = Field(
        default_factory=lambda: [
            "We strongly advise against making unnecessary printed copies of sacred texts "
            "and art containing divine names as these copies must be regarded with "
            "reverence, complicating their casual treatment and disposal.",
            _GENIZAH_STATEMENT,
        ]
    )

    @field_validator("electronic", "print")
    @classmethod
    def validate_statements(cls, v: list[str]) -> list[str]:
        return _no_blank_lines(v)


_GENIZAH_STATEMENT = (
    "If you must dispose of a printed sacred text (one containing Divine Names), please "
    "locate the closest _genizah_ (often established by a synagogue) and contact its "
    "custodians for further instructions."
)


class DistributionSettings(BaseModel):
    """ Who distributes the book, and how to treat it once read.

    Either part is `none` to leave it out.
    """

    model_config = ConfigDict(extra="forbid")
    notice: Union[DistributionNotice, Literal["none"]] = Field(
        default_factory=DistributionNotice
    )
    back_notice: Union[BackNotice, Literal["none"]] = Field(default_factory=BackNotice)


class SettingsYaml(BaseModel):
    """ A settings file, whole.

    Unknown keys are refused at every level: a mistyped setting that is quietly
    ignored produces a document that is missing what was asked for, with nothing
    to say why.
    """

    model_config = ConfigDict(extra="forbid")

    # What this settings file makes and how it differs from the book's other settings files
    # (e.g. annual vs. triennial readings for the same humash). Free text, for people.
    description: Optional[str] = None
    # The processor versions that build this book as it should be, as PEP 440 writes them
    # (`>=0.7.0`). An older processor refuses the file rather than build a broken book: the
    # settings and the processor that reads them are released separately, and a release
    # can pair a book with a processor that predates a fix it depends on.
    requires_processor: Optional[str] = None
    book: Optional[BookTarget] = None
    # Empty, the compiler gives priority to the project of the file it compiles.
    priority: Prioritizations = Field(default_factory=Prioritizations)
    annotations: list[str] = Field(default_factory=list)
    print_once: PrintOnceSettings = Field(default_factory=PrintOnceSettings)
    parallel: Optional[ParallelConfig] = None
    readings: ReadingSettings = Field(default_factory=ReadingSettings)
    typography: TypographyConfig = Field(default_factory=TypographyConfig)
    declarations: dict[str, dict[str, DeclarationFeatureValue]] = Field(default_factory=dict)
    electronic: ElectronicSettings = Field(default_factory=ElectronicSettings)
    distribution: DistributionSettings = Field(default_factory=DistributionSettings)
    # The forms a release builds this book in: `html`, the electronic book, and `pdf`, the
    # printed one. A book read only on a device, its day chosen there, lists just `html`.
    formats: list[Literal["html", "pdf"]] = Field(default_factory=lambda: ["html", "pdf"])

    @field_validator("requires_processor")
    @classmethod
    def validate_requires_processor(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        parse_requirement(v)
        installed = processor_version()
        if installed is None:
            raise ValueError(
                f"this settings file requires opensiddur-processor {v}, and this "
                "opensiddur-processor is not installed, so its version is unknown "
                "(uv sync installs it)")
        if not satisfies(v, installed):
            raise ValueError(
                f"this settings file requires opensiddur-processor {v}; this is {installed}. "
                "Build it with a later processor (in a checkout of main, `uv sync` updates "
                "the version installed)")
        return v

    @model_validator(mode="after")
    def validate_scan_viewer_has_links(self) -> "SettingsYaml":
        if (self.electronic.scan_viewer != "off"
                and self.typography.markers.scan_links.placement is ScanLinkPlacement.NONE):
            raise ValueError(
                "electronic.scan_viewer opens the links to the scans, and "
                "typography.markers.scan_links.placement is `none`, so there are none to "
                "open. Set a placement (inline or margin), or leave the viewer off.")
        return self

    @field_validator("formats")
    @classmethod
    def validate_formats(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("a book must be built in at least one format")
        if len(set(v)) != len(v):
            raise ValueError(f"a format is listed twice: {v}")
        return v

    @field_validator("annotations")
    @classmethod
    def validate_annotations(cls, v: list[str], info: ValidationInfo) -> list[str]:
        return _validate_projects(v, info)

    @field_validator("declarations")
    @classmethod
    def validate_declarations(
        cls, v: dict[str, dict[str, DeclarationFeatureValue]]
    ) -> dict[str, dict[str, DeclarationFeatureValue]]:
        # Each type and feature in the opensiddur: namespace must be registered, and each
        # value of the registered kind. A misspelt feature is otherwise a setting nothing reads.
        problems = [
            problem
            for fs_type, features in v.items()
            for feature, value in features.items()
            for problem in feature_registry.check_yaml_value(fs_type, feature, value)
        ]
        if problems:
            raise ValueError("; ".join(problems))
        return v

def read_settings(
    settings_file: Path,
    project_directory: Optional[Path] = None,
    resolve_fonts: bool = True,
    check_projects: bool = True,
) -> SettingsYaml:
    """ Read and validate a settings file, without loading it into linear data. """
    with open(settings_file, 'r', encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return validate_settings(data, project_directory, resolve_fonts, check_projects)


def validate_settings(
    data: object,
    project_directory: Optional[Path] = None,
    resolve_fonts: bool = True,
    check_projects: bool = True,
) -> SettingsYaml:
    """ Validate a settings file's contents, as YAML has read them.

    ``resolve_fonts=False`` skips checking that the font chains it names are installed
    here — for a reader that never selects a font, such as the compiler.
    ``check_projects=False`` skips checking that the projects and files it names exist.
    """
    project_directory = Path(project_directory or PROJECT_DIRECTORY).resolve()
    return SettingsYaml.model_validate(
        data,
        context={
            "project_directory": project_directory,
            RESOLVE_FONTS: resolve_fonts,
            CHECK_PROJECTS: check_projects,
        },
    )


def load_settings(
    settings_file: Path,
    linear_data: Optional[LinearData] = None,
    project_directory: Optional[Path] = None,
) -> LinearData:
    """ Load settings into linear data from a YAML file. """
    project_directory = Path(project_directory or PROJECT_DIRECTORY).resolve()
    # The compiler typesets nothing, so whether this machine has a font is the output
    # stage's question, asked there (an electronic book never asks it at all).
    settings = read_settings(
        settings_file, project_directory=project_directory, resolve_fonts=False
    )
    linear_data = linear_data or get_linear_data()
    _apply_project_directory(linear_data, project_directory)
    linear_data.project_priority = settings.priority.transclusion
    linear_data.instruction_priority = settings.priority.instructions
    linear_data.abbreviation_reading = settings.readings.abbreviations
    linear_data.error_reading = settings.readings.errors
    linear_data.annotation_projects = settings.annotations
    linear_data.annotation_print_once_types = settings.print_once.note_types()
    if settings.parallel:
        linear_data.parallel_projects = settings.parallel.projects
        linear_data.parallel_column_order = settings.parallel.column_order
    if settings.declarations:
        entries = yaml_to_declaration_entries(settings.declarations)
        if linear_data.defer_reader_settings:
            # The reader's settings are the book's defaults, which the reader can change; they
            # reach the electronic book from the settings file, not from the compile. They stay
            # on the stack, undefined, so that they still rank as explicit: a derivation does
            # not override them, any more than it would in print.
            entries = [
                entry.model_copy(update={"value": Undefined})
                if is_reader_supplied(entry.fs_type) else entry
                for entry in entries
            ]
        CompilerProcessor.load_init_settings(linear_data, entries)
    else:
        recalculate_derived_settings(linear_data, trigger=SettingChangeTrigger.INIT)
    return linear_data


def load_default_settings(
    project: str,
    file_name: str,
    linear_data: Optional[LinearData] = None,
    project_directory: Optional[Path] = None,
) -> LinearData:
    """ Load default settings into linear data. """
    project_directory = Path(project_directory or PROJECT_DIRECTORY).resolve()
    linear_data = linear_data or get_linear_data()
    _apply_project_directory(linear_data, project_directory)
    linear_data.project_priority = [project]
    linear_data.instruction_priority = [project]
    linear_data.annotation_projects = [project]
    recalculate_derived_settings(linear_data, trigger=SettingChangeTrigger.INIT)
    return linear_data
