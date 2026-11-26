"""Which opensiddur-processor this is, and whether it is the one a settings file needs."""

from importlib.metadata import PackageNotFoundError, version

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

DISTRIBUTION = "opensiddur-processor"


def processor_version() -> str | None:
    """The installed processor's version (`0.7.0.dev0` on main between releases), or None when
    it is run from a tree that was never installed."""
    try:
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        return None


def parse_requirement(requirement: str) -> SpecifierSet:
    """A version requirement, as PEP 440 writes one: `>=0.7.0`, `>=0.7,<0.9`."""
    try:
        specifiers = SpecifierSet(requirement)
    except InvalidSpecifier as e:
        raise ValueError(f"{requirement!r} is not a version requirement, such as `>=0.7.0`") from e
    if not len(specifiers):
        raise ValueError("an empty version requirement requires nothing; leave it out instead")
    return specifiers


def satisfies(requirement: str, installed: str) -> bool:
    """Whether a processor of version `installed` meets `requirement`.

    A development version counts as the release it is the development of: main between 0.6.0
    and 0.7.0 is 0.7.0.dev0, and has what 0.7.0 will, so it meets `>=0.7.0`. A 0.6.0 does not.
    """
    release = Version(Version(installed).base_version)
    return parse_requirement(requirement).contains(release, prereleases=True)
