""" Resolver for urn:x-opensiddur: URIs.
"""
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.exporter.refdb import Reference, ReferenceDatabase


class ResolvedUrn(BaseModel):
    project: str
    file_name: str
    urn: str
    element_path: str
    end_element_path: str | None = None
    end_includes_tail: bool = False


class ResolvedUrnRange(BaseModel):
    start: ResolvedUrn
    end: ResolvedUrn

    @property
    def project(self) -> str:
        return self.start.project


def split_project(urn: str) -> tuple[str, str | None]:
    """``urn`` without its ``@project`` suffix, and the project it names (None if none).

    The suffix is everything after the last ``@``, so a project name may hold any character
    but ``@`` itself.
    """
    if '@' not in urn:
        return urn, None
    bare, project = urn.rsplit('@', 1)
    return bare, project


def with_project(urn: str, project: str | None) -> str:
    """``urn`` with an ``@project`` suffix, replacing any it already has."""
    bare, _ = split_project(urn)
    return f"{bare}@{project}" if project else bare


def split_range(ranged_urn: str) -> tuple[str, str] | None:
    """Split a ranged URN into its start and end URNs.

    A range is written with '-' in a path component. The part before the dash closes the
    start URN; what follows names the end. There are two ways to name the end:

    **Relative** — the end replaces that many trailing components of the start, which leaves
    it at the same depth::

        genesis/1/1-2      → genesis/1/1  … genesis/1/2
        genesis/1/1-2/3    → genesis/1/1  … genesis/2/3
        nahum/2/2/b-2/3/a  → nahum/2/2/b  … nahum/2/3/a

    **Absolute** — an end that begins with '/' replaces the whole path below the component
    carrying the namespace and the work, so the two ends need not be at the same depth::

        nahum/2/2/b-/2/5   → nahum/2/2/b  … nahum/2/5
        genesis/1/1-/3     → genesis/1/1  … genesis/3

    Write the absolute form whenever the ends are at different depths: a sub-verse start
    with a whole-verse end has no relative spelling, since a relative end always lands at
    the start's own depth. This is also why a range cannot cross works — the absolute form
    keeps the start's namespace-and-work component, and the relative form never touches it.

    Args:
        ranged_urn: A URN, with or without range notation. Any '@project' suffix must
                    already have been stripped.

    Returns:
        (start_urn, end_urn), or None if `ranged_urn` names no range at all.

    Raises:
        ValueError: if it names a range but not a well-formed one.
    """
    parts = ranged_urn.split('/')

    # Index 0 holds the scheme, namespace and work ("urn:x-opensiddur:text:bible:genesis"),
    # whose dashes ("x-opensiddur") never mark a range. Only the path components below it
    # are candidates, and the last dash-bearing one wins.
    range_start_idx = None
    for i in range(len(parts) - 1, 0, -1):
        if '-' in parts[i]:
            range_start_idx = i
            break

    if range_start_idx is None:
        return None

    start_value, end_spec_start = parts[range_start_idx].split('-', 1)
    if not start_value:
        raise ValueError(f"Range has no start: {ranged_urn!r}")
    start_urn = '/'.join(parts[:range_start_idx] + [start_value])

    remaining_parts = parts[range_start_idx + 1:]
    end_spec = end_spec_start
    if remaining_parts:
        end_spec += '/' + '/'.join(remaining_parts)

    if end_spec.startswith('/'):
        end_components = end_spec[1:].split('/')
        if not all(end_components):
            raise ValueError(f"Absolute range end is empty: {ranged_urn!r}")
        end_parts = [parts[0]] + end_components
    else:
        if not end_spec:
            raise ValueError(f"Range has no end: {ranged_urn!r}")
        end_components = end_spec.split('/')
        # A relative end replaces trailing components of the start, so it can never be
        # deeper than the start is. Before the absolute form existed this case built an end
        # URN with the scheme sliced off it, which then resolved to nothing, silently.
        base = range_start_idx - len(end_components) + 1
        if base < 1:
            raise ValueError(
                f"Relative range end {end_spec!r} is deeper than the start it replaces in "
                f"{ranged_urn!r}; state it absolutely as -/{end_spec}"
            )
        end_parts = parts[:base] + end_components

    return start_urn, '/'.join(end_parts)


#: The namespace whose URNs reach below a whole division: a Bible verse can be divided into
#: half-verses and named parts. Only there does a coarser URN stand for "the same text, less
#: finely divided"; elsewhere the parent of a URN is a different, larger text.
_SUB_VERSE_NAMESPACE = "urn:x-opensiddur:text:bible:"

#: book/chapter/verse: the components of a whole verse below the namespace.
_VERSE_DEPTH = 3


def _below_the_verse(urn: str) -> bool:
    """Whether ``urn`` names a point inside a numbered verse: book/chapter/verse/part.

    Other Bible URNs run deeper too -- a parashah's aliyot, a reading's haftarah -- but their
    parents are not verses, and do not contain them the way a verse contains its half.
    """
    if not urn.startswith(_SUB_VERSE_NAMESPACE):
        return False
    components = urn[len(_SUB_VERSE_NAMESPACE):].split("/")
    return (len(components) > _VERSE_DEPTH
            and components[1].isdigit() and components[2].isdigit())


def coarsen(urn: str, resolves: Callable[[str], bool] | None = None) -> str | None:
    """The verse that contains a sub-verse reference, or None if there is no such fallback.

    A project need not carry every division another project does: a translation has no
    accents, so it can place no half-verses, and a reference to one has to fall back on the
    verse that contains it or the translation drops out of the page altogether. Reading a
    whole verse where half was asked for is the behaviour that was there before sub-verse
    URNs existed; what is new is that the caller knows it happened and can say so.

    Only a point below a Bible verse is coarsened. A whole verse is not widened to its
    chapter, and the parent of any other URN is a different text, not a coarser division of
    the same one: falling back from a part of the Amidah to the whole Amidah would print the
    wrong thing.

    In a range each end is coarsened by itself, and only if it is below the verse and does
    not resolve (``resolves`` says which do; without it, every end below the verse is taken
    not to). An end that is already a verse stays where it is, so ``2:2b-2:5`` falls back to
    ``2:2-2:5`` rather than to the rest of chapter 2. The result is stated absolutely, since
    the two ends may no longer be at the same depth.
    """
    urn, project_specifier = split_project(urn)

    try:
        split = split_range(urn)
    except ValueError:
        return None

    def coarser(one: str) -> str | None:
        """``one`` less its sub-verse component, or None if it is to be kept."""
        if not _below_the_verse(one):
            return None
        if resolves is not None and resolves(with_project(one, project_specifier)):
            return None
        return one.rpartition('/')[0]

    if split is None:
        coarsened = coarser(urn)
    else:
        start, end = split
        new_start, new_end = coarser(start), coarser(end)
        if new_start is None and new_end is None:
            return None
        start, end = new_start or start, new_end or end
        _work, _, below = end.partition('/')
        coarsened = f"{start}-/{below}"

    if coarsened is None:
        return None
    return with_project(coarsened, project_specifier)


class UrnResolver:
    """Resolves URNs to their corresponding project and file paths."""
    
    def __init__(self, reference_database: ReferenceDatabase | None = None):
        """Initialize the URN resolver with a SQLite database.
        
        Args:
            database_path: Path to the SQLite database file
        """
        self.database = reference_database or ReferenceDatabase()
        
    def resolve(self, urn: str) -> list[ResolvedUrn]:
        """Resolve a URN to its project and file name.
        
        Args:
            urn: The URN to resolve (from corresp attribute).
                 Can include project specifier: 'urn@project'
            
        Returns:
            List of ResolvedUrn objects. Empty list if not found.
            May contain multiple entries if URN exists in multiple projects
            (when no project specifier is provided).
        """
        # Handle URNs with '@' sign: 'urn@project'
        actual_urn, project = split_project(urn)
        if project:
            mappings = self.database.get_urn_mappings(actual_urn, project)
        else:
            mappings = self.database.get_urn_mappings(actual_urn)
        
        return [
            ResolvedUrn(
                project=row.project,
                file_name=row.file_name,
                urn=actual_urn,
                element_path=row.element_path,
                end_element_path=row.end_element_path,
                end_includes_tail=row.end_includes_tail
            )
            for row in mappings
        ]
    
    def resolve_range(self, ranged_urn: str) -> list[ResolvedUrnRange | ResolvedUrn]:
        """Resolve a ranged URN to start and end URNs, or a non-ranged URN.
        
        The range notation itself is parsed by `split_range`, which documents the relative
        and absolute forms of a range end.

        If the URN names no range, it is treated as a non-ranged URN and resolve() is
        called instead.

        Args:
            ranged_urn: A URN with range notation (e.g., 'urn:.../1/1-2', 'urn:.../1/1-2/3@project'
                       or 'urn:.../2/2/b-/2/5') or a non-ranged URN (e.g., 'urn:.../genesis/1/1')

        Returns:
            List of ResolvedUrnRange objects for ranged URNs, or list of ResolvedUrn objects
            for non-ranged URNs. May contain multiple entries if the URN exists in multiple
            projects (when no project specifier is provided).
            Returns empty list if start and end don't resolve to any matching project/file
            combinations.

        Raises:
            ValueError: if the URN names a range but not a well-formed one.
        """
        # Handle @project notation
        ranged_urn, project_specifier = split_project(ranged_urn)

        split = split_range(ranged_urn)

        if split is None:
            # Not a range. Add back the project specifier if present and resolve it alone.
            urn_to_resolve = ranged_urn
            if project_specifier:
                urn_to_resolve = f"{ranged_urn}@{project_specifier}"
            return self.resolve(urn_to_resolve)

        start_urn, end_urn = split

        # Add back the project specifier if present
        if project_specifier:
            start_urn = f"{start_urn}@{project_specifier}"
            end_urn = f"{end_urn}@{project_specifier}"
        
        # Resolve both URNs
        start_resolved_list = self.resolve(start_urn)
        end_resolved_list = self.resolve(end_urn)
        
        # Check if both resolved
        if not start_resolved_list or not end_resolved_list:
            return []
        
        # Find all matching project/file combinations
        # Create a dict to map (project, file_name) -> end_resolved
        end_dict = {(end_resolved.project, end_resolved.file_name): end_resolved 
                    for end_resolved in end_resolved_list}
        ranges = [ResolvedUrnRange(start=start_resolved, end=end_dict.get((start_resolved.project, start_resolved.file_name)))
                  for start_resolved in start_resolved_list
                  if (start_resolved.project, start_resolved.file_name) in end_dict]

        if not ranges:
            # Both ends exist, but no project has them in one file. That is not a missing
            # URN, and "not found" would send the author looking for the wrong thing.
            both = ({r.project for r in start_resolved_list}
                    & {r.project for r in end_resolved_list})
            if both:
                raise ValueError(
                    f"The start and end of {ranged_urn} are in different files in "
                    f"{sorted(both)}; a range must lie within one file")

        return ranges
    
    def get_urns_by_project(self, project: str) -> list[ResolvedUrn]:
        """Get all URN mappings for a specific project.
        
        Args:
            project: The project name to filter by
            
        Returns:
            List of dictionaries containing urn, project, and file_name
        """
        mappings = self.database.get_urn_mappings(project=project)
        return [
            ResolvedUrn(
                project=mapping.project,
                file_name=mapping.file_name,
                urn=mapping.urn,
                element_path=mapping.element_path,
                end_element_path=mapping.end_element_path,
                end_includes_tail=mapping.end_includes_tail
            )
            for mapping in mappings
        ]
    
    
    @classmethod
    def prioritize_range(cls, 
        resolved_urns: list[ResolvedUrn | ResolvedUrnRange | Reference],
        project_priority: list[str],
        return_all: bool = False) -> ResolvedUrn | ResolvedUrnRange | Reference | list[ResolvedUrn | ResolvedUrnRange | Reference] | None:
        """Prioritize a list of resolved URNs or URN ranges based on a project priority list.
        
        Args:
            resolved_urns: List of ResolvedUrn or ResolvedUrnRange objects
            project_priority: List of project names in priority order
            return_all: If True, return all resolved URNs or URN ranges, otherwise return the most prioritized one
        Returns:
            The most prioritized ResolvedUrn or ResolvedUrnRange object.
            If none of the URNs are prioritized, return None.
        """
        # map a numeric priority to a project name
        priorities = dict(zip(project_priority, range(len(project_priority))))
        def _project_name(urn) -> str:
            return urn.project
        sorted_urns = sorted([
            r for r in resolved_urns 
            if priorities.get(_project_name(r)) is not None
            ], 
            key=lambda x: priorities.get(_project_name(x)))
        if len(sorted_urns) > 0:
            return sorted_urns[0] if not return_all else sorted_urns
        return None

    @classmethod
    def get_path_from_urn(cls, resolved_urn: ResolvedUrn, project_directory: Path = PROJECT_DIRECTORY) -> Path:
        """Get the path from a URN.
    
        Args:
            resolved_urn: The ResolvedUrn
            
        Returns:
            The path
        """
        return project_directory / resolved_urn.project / resolved_urn.file_name


