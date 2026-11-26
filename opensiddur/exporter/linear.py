""" Singleton class to hold data from linear processing.

Linear processing treats the entire hierarchy as a single pass,
so the data are the same independent of depth.
"""
from enum import StrEnum
from fractions import Fraction
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from opensiddur.exporter.cache import XMLCache

# Literal values allowed in exporter settings YAML ``declarations`` (null → Undefined).
DeclarationFeatureValue: TypeAlias = int | float | bool | str | None


class UndefinedType:
    """Sentinel for undefined / any-value feature semantics."""

    _instance: "UndefinedType | None" = None

    def __new__(cls) -> "UndefinedType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "Undefined"


Undefined = UndefinedType()


def parse_numeric_literal(raw: str) -> int | float:
    """Parse a tei:numeric @value / @max literal.

    teidata.numeric allows an integer, a decimal (with an exponent) or a fraction such as
    ``1/2``. A fraction that comes out whole is an integer.
    """
    text = raw.strip()
    try:
        return int(text)
    except ValueError:
        pass
    if "/" in text:
        numerator, _, denominator = text.partition("/")
        try:
            quotient = Fraction(int(numerator), int(denominator))
        except (ValueError, ZeroDivisionError):
            raise ValueError(f"not a teidata.numeric: {raw!r}") from None
        if numerator != numerator.strip() or denominator != denominator.strip():
            raise ValueError(f"not a teidata.numeric: {raw!r}")
        return int(quotient) if quotient.denominator == 1 else float(quotient)
    return float(text)


class NumericValue(BaseModel):
    """Parsed tei:numeric value, optionally with inclusive upper bound (@max)."""

    value: int | float
    max_value: int | float | None = None


class TwilightValue(BaseModel):
    """A derived value that differs between the two days bein hashmashot lies between.

    Between sunset and nightfall it is doubtful which day it is, and the day has some of the
    character of both. A feature computed from the date then holds the value it has on the
    day that is ending and the one it has on the day that is beginning. Only a derivation
    produces one: a volume declares a value, never two. A condition on it is decided only
    if it comes out the same on both days (condition_eval.evaluate_condition).
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    ending: Any
    starting: Any

    def on_day(self, day: int) -> Any:
        """The value on the ending day (0) or the starting day (1)."""
        return self.starting if day else self.ending


class ConditionalSettingEntry(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    declare_id: str
    fs_type: str
    feature_name: str
    value: int | float | bool | str | NumericValue | TwilightValue | UndefinedType
    source: Literal["init", "declared", "derived"]
    contributors: set[str] = Field(default_factory=set)


class ConditionalScope(BaseModel):
    """Open j:conditional scope and its evaluation result."""

    scoped_id: str
    result: str  # TriState value


class ParallelColumnOrder(StrEnum):
    PRIMARY_FIRST = "primary_first"
    PRIMARY_LAST = "primary_last"


class AbbreviationReading(StrEnum):
    ABBREVIATED = "abbreviated"
    EXPANDED = "expanded"


class ErrorReading(StrEnum):
    """Which form of an edition error to read: the misprint as printed, or its correction."""
    PRINTED = "printed"
    CORRECTED = "corrected"


class LinearData(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True)

    abbreviation_reading: AbbreviationReading = AbbreviationReading.ABBREVIATED
    error_reading: ErrorReading = ErrorReading.CORRECTED

    # Logical headed-division nesting, preserved while parallel assembly splits containers.
    heading_depth: int = 0

    # parsed XML cache
    xml_cache: XMLCache = Field(default_factory=XMLCache)
    # scoped conditional setting stack (init, declared, derived entries)
    conditional_settings: list[ConditionalSettingEntry] = Field(default_factory=list)
    # open j:conditional scopes (innermost last)
    conditional_scope_stack: list[ConditionalScope] = Field(default_factory=list)
    # the ranges being transcluded, outermost first: (project, file, start path, end path)
    transclusion_chain: list[tuple[str, str, str, str]] = Field(default_factory=list)
    # project priority for URN resolution of texts
    project_priority: list[str] = Field(default_factory=list)
    # project priority for URN resolution of instructions
    instruction_priority: list[str] = Field(default_factory=list)
    # projects from which to include annotations (not a priority list)
    annotation_projects: list[str] = Field(default_factory=list)
    # note @type values printed only at their first occurrence in the book (settings `print_once`)
    annotation_print_once_types: set[str] = Field(default_factory=set)
    # (project, file_name, element_path) of every print-once annotation already printed.
    # Book-global: never truncated by settings checkpoints, only rolled back when a parallel
    # counterpart compilation fails and its output is discarded.
    printed_annotations: set[tuple[str, str, str]] = Field(default_factory=set)
    # processing context includes processor-specific data. Because there is recursion, it acts as a stack.
    processing_context: list[dict[str, Any]] = Field(default_factory=list)
    # projects to search for parallel text content (in priority order)
    parallel_projects: list[str] = Field(default_factory=list)
    # column order for parallel text display
    parallel_column_order: ParallelColumnOrder = Field(default=ParallelColumnOrder.PRIMARY_FIRST)
    # >0 while a parallel sub-compilation is in progress. Parallel blocks end at every external
    # transclusion and never nest, so a sub-compilation must not re-trigger parallel processing.
    # Ambient on LinearData rather than per-processor: nested processors are constructed in five
    # places and a per-instance flag is silently dropped by all of them.
    parallel_compilation_depth: int = 0
    # Every contributor credit met while compiling, in the order met, as
    # (resp key, name/@ref, name, resp wording). A transcluded document contributes its
    # text and not its header, so its credits would otherwise be lost at the moment its
    # words are taken -- and a reader of the compiled text would see the credits of the
    # one file that happened to be the root.
    credits: list[tuple[str, str, str, str]] = Field(default_factory=list)
    # files whose reference-database rows have been checked against their contents
    index_checked: set[tuple[str, str]] = Field(default_factory=set)
    # Problems with the declared dates already reported, so that a compile reports each once.
    date_warnings: set[str] = Field(default_factory=set)
    # Compiling for an electronic book: the settings the reader supplies (client_settings) are
    # left undecided, for the reader's device to resolve, and each retained conditional records
    # the values the compile did know (p:pinned).
    defer_reader_settings: bool = False

_linear_data = LinearData()

def reset_linear_data():
    global _linear_data
    _linear_data = LinearData()

def get_linear_data() -> LinearData:
    global _linear_data
    return _linear_data
