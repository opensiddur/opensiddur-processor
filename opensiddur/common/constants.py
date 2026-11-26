from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# The sourcetexts and opensiddur-projects repositories are git submodules of this one,
# checked out at the repository root. Each keeps its content in a subdirectory.
SOURCETEXTS_ROOT = REPO_ROOT / "sourcetexts" / "sources"
PROJECT_DIRECTORY = REPO_ROOT / "opensiddur-projects" / "project"
# Settings files for the printed books, one per book; see opensiddur.exporter.books.
SETTINGS_DIRECTORY = REPO_ROOT / "opensiddur-projects" / "settings"
INDEX_DB_DIRECTORY = REPO_ROOT / "database"

# Untracked scratch space for large or derived files that should never enter a
# repository — scanned PDFs fetched for human comparison, for instance. It sits
# beside the repositories rather than inside one, per the worktree layout in the
# top-level CLAUDE.md: <repos>/<repository>/<branch>/.
OUTPUT_DIRECTORY = REPO_ROOT.parent.parent / "output"
