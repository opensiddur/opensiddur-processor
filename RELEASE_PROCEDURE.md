# Release procedure

There are two kinds of release, versioned separately:

- **Code releases** are `v<major>.<minor>.<patch>` tags on this repository (`opensiddur-processor`),
  cut by hand as described below. The tag's commit pins exact commits of the `sourcetexts` and
  `opensiddur-projects` submodules: a record of the data the code was tested against.
- **Book releases** are date tags, `vYYYYMMDD`, on `opensiddur-projects`, made monthly by a
  workflow. The books (electronic and printed) are built from that commit with the latest code
  release and attached to it. See [Book releases](#book-releases).

## Versioning policy

- **0.x series** (current): a release normally bumps the **minor** version
  (`0.1.0 -> 0.2.0 -> 0.3.0 ...`). Backwards compatibility is not promised between releases.
  A release that only fixes bugs in the previous one, and adds nothing else, bumps the
  **patch** version instead (`0.5.0 -> 0.5.1`); cut it with `--patch`.
- **1.0.0 and above**: strict [Semantic Versioning](https://semver.org/). Choose the bump level
  deliberately — major for incompatible changes, minor for backwards-compatible features, patch
  for backwards-compatible fixes.
- **Between releases** `main` is the *development* of the next release: after `0.6.0`,
  `pyproject.toml` says `0.7.0.dev0`. That is the version a settings file's `requires_processor`
  is checked against, as the release it is the development of: main meets `>=0.7.0`, and the
  `v0.6.0` tag does not. A release from a development version releases the version it names
  (the default, or the level it names); `--major` jumps past it. `--patch` releases a fix of
  the last release tagged (`0.6.0 -> 0.6.1`), and leaves `main` the development it was.
  The check compares the release a development version leads to, so every `main` since 0.6.0
  meets `>=0.7.0`, whether or not the fix a book needs has been merged yet: the requirement
  tells released processors apart, not one `main` from another.

## Before releasing

Work from an up-to-date worktree on `main`, per this project's [worktree convention](../CLAUDE.md):

```bash
git worktree add ../main origin/main   # if you don't already have a main worktree
cd ../main
git fetch origin
git status                              # must be clean
git submodule update --init
uv sync --all-groups
bash scripts/build-schema.sh
uv run coverage run -m unittest discover -s opensiddur/tests -v
uv run coverage report -m
uv build                                # writes to dist/, which is gitignored
```

Confirm:
- The working tree is clean and `main` is up to date with `origin/main`.
- The full test suite passes.
- `uv build` succeeds. Nothing publishes the distributions it produces; this only checks that the
  package still builds from the tree being tagged.
- `sourcetexts/` and `opensiddur-projects/` are on the commits you intend to ship — if you need
  a specific commit rather than the tip of each repo's default branch, update the submodule by
  hand first (`cd sourcetexts && git checkout <commit>`) and commit that.
- `CHANGELOG.md`'s `## [Unreleased]` section accurately describes what's shipping. The release
  will fail if it's empty.
- You have push access to `origin` and `gh auth status` shows you're logged in (needed for the
  GitHub Release step).

## Releasing

Dry run first — this prints every command and file change and touches nothing:

```bash
uv run python -m opensiddur.release --dry-run
```

Review the printed version bump, the changelog diff, and the submodule commits it would pin.
Then run it for real:

```bash
uv run python -m opensiddur.release
```

Flags:
- `--minor` / `--major` / `--patch` — choose the bump level. Below 1.0.0 this defaults to
  `--minor` (pass `--patch` for a bugfix release); at 1.0.0 and above one of these (or `--version`) is required.
- `--version X.Y.Z` — release an exact version instead of bumping.
- `--no-publish` — tag and push, but skip creating the GitHub Release.
- `--dry-run` — as above.

What it does, in order:
1. Reads the current version from `pyproject.toml`.
2. Computes the next version and checks that its tag doesn't already exist locally or on
   `origin`.
3. Runs `git submodule update --init --remote` to move `sourcetexts` and `opensiddur-projects`
   to the tip of the branch each tracks (`master` and `main` respectively — see `.gitmodules`).
4. Writes the new version into `pyproject.toml`.
5. Rolls `CHANGELOG.md`'s `[Unreleased]` section into a new `## [X.Y.Z] - <date>` section,
   appends the pinned submodule commits to it, and leaves a fresh empty `[Unreleased]` above it.
6. Commits `pyproject.toml`, `CHANGELOG.md`, and the two submodule pointers as `Release vX.Y.Z`.
7. Creates an annotated tag `vX.Y.Z` with the new changelog section as its message.
8. If the version it started from was a development version, writes the development of the
   next release (`0.8.0.dev0` after `0.7.0`) into `pyproject.toml` and commits it as
   `Begin 0.8.0.dev0`, after the tag, so the tag is the release and the branch goes on. After
   a patch release it writes back the development it started from (`0.7.0.dev0` after
   `0.6.1`).
9. Pushes the branch and the tag to `origin`.
10. Creates a GitHub Release for the tag via `gh release create`, using the same notes (skipped
   with `--no-publish`).

A code release builds no books. The next book release builds them with it, even when
opensiddur-projects has not changed.

## After releasing

- **Re-lock and push `uv.lock`.** The release script writes the new versions into `pyproject.toml`
  (steps 4 and 8) but never re-locks, so `uv.lock` still records the *previous* version for the
  `opensiddur-processor` package. Correct it so the two agree (on `main`, that is the next
  development version):

  ```bash
  uv lock
  git add uv.lock
  git commit -m "Update uv.lock for vX.Y.Z"
  git push origin main
  ```

  This lands after the tag, so the tagged commit itself still carries the stale lockfile. That is
  cosmetic — the recorded version of the project's own package does not affect how dependencies
  resolve — but skipping it means the next person to run `uv sync --all-groups` gets a modified
  `uv.lock` in their working tree, which collides with the "working tree must be clean" check in
  *Before releasing* and looks like an unrelated change in their branch.

- Check the [releases page](https://github.com/opensiddur/opensiddur-processor/releases) and the pushed
  tag.
- If the books should not wait for the first of the month, start a book release now (below).
- Confirm `git submodule status` on the tag shows the commits you expected.
- If a downstream worktree needs the release, `git fetch --tags` and check out the tag, then
  `git submodule update --init`.

## Book releases

`opensiddur-projects/.github/workflows/release.yml` runs at 00:00 UTC on the first of each
month. It calls this repository's `.github/workflows/release-projects.yml`, which:

1. Finds the latest code release (the newest `vX.Y.Z` tag here) and the last book release (the
   newest `vYYYYMMDD` tag on opensiddur-projects).
2. Stops if there is nothing new: opensiddur-projects `main` has not changed since the last book
   release, other than its `DOWNLOADS.md` (step 7), and that release was built with the same code
   release. Each book release's notes
   record it in a `Built with opensiddur-processor vX.Y.Z` line, which this step reads.
3. Lists the settings files in `opensiddur-projects/settings/<book>/` with that code release
   (`books --list`). A settings file's `requires_processor:` says which code releases can
   build it; a book that release does not meet is left out until one does.
4. Creates a draft release `vYYYYMMDD` (today's UTC date) at the `main` commit, with notes that
   list the opensiddur-projects commits since the last book release.
5. Starts one `release-book.yml` job per settings file. It builds the book in the formats its
   settings' `formats:` lists, both unless it says otherwise, and attaches them to the release:
   - the electronic book, `<book>-<variant>-vYYYYMMDD.html`, first, which takes seconds;
   - then the printed book, `<book>-<variant>-vYYYYMMDD.pdf`.
6. Publishes the release once every book has finished. Publishing creates the tag. A run
   that is cancelled leaves the draft unpublished; finish it by rebuilding it with its tag.
7. Rewrites `DOWNLOADS.md` in opensiddur-projects, the list of the newest release's books: each
   book's title and description, from its settings file at the release's commit, and links to its
   electronic and printed books on the release. `main` takes changes only by pull request, so
   the workflow pushes a `downloads/vYYYYMMDD` branch, opens its pull request and merges it.
   Rebuilding the newest release rewrites the list too; rebuilding an older one leaves it alone.
   If the merge is refused (for instance, because the branch protection changed), merge the
   leftover `downloads/vYYYYMMDD` pull request by hand.

The books build in parallel, each with its own log and status; a large one (the full humash)
takes well over an hour. A printed book that fails leaves its electronic book attached, and a
book that fails is not attached at all. Its job is red, but the release is still published.
Its `book-log-<book>-<variant>-vYYYYMMDD` artifact has the compiler and LaTeX output, under
`html/` and `pdf/`.

The first code release that can build books is v0.7.0: v0.6.0 and earlier refuse the
`requires_processor:` key.

Run it by hand from opensiddur-projects:

```bash
# A book release now, if there is anything new:
gh workflow run release.yml -R opensiddur/opensiddur-projects
# ...even if there is nothing new:
gh workflow run release.yml -R opensiddur/opensiddur-projects -f force=true
# Rebuild every book of an existing release, or one, replacing its assets:
gh workflow run release.yml -R opensiddur/opensiddur-projects -f tag=vYYYYMMDD
gh workflow run release.yml -R opensiddur/opensiddur-projects -f tag=vYYYYMMDD -f book=<book>/<variant>
```

A rebuild uses the projects commit and the code release that the release records. A fix that
lands later ships with the next book release. A second release on the same day is refused:
rebuild that day's release instead.

GitHub turns off scheduled workflows in a repository with no activity for 60 days. If the
monthly run stops, turn it back on from opensiddur-projects' Actions tab.

## Undoing a bad release

If something is wrong before anyone has pulled the tag:

```bash
gh release delete vX.Y.Z --yes           # if a GitHub Release was created
git push origin :refs/tags/vX.Y.Z        # delete the remote tag
git tag -d vX.Y.Z                        # delete the local tag
git revert <release-commit>              # or reset, if it hasn't been pulled elsewhere
git push origin main
```

Prefer `git revert` over rewriting `main` history once the release commit has been pushed, so
that anyone who already fetched it doesn't end up with a diverged branch.
