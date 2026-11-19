# Release process

CMF Dev Studio follows Semantic Versioning and a Git Flow-style workflow. Development pull requests target `develop`; stable releases are published from `main` by `.github/workflows/release.yml`.

The commands below use v0.4.0 as an example. Replace the target version and previous tag for future releases. Run commands from the repository root unless indicated otherwise.

## 1. Prepare the release branch

Ensure the intended feature PRs are merged, the working tree is clean and the checks are green.

```bash
git switch develop
git pull --ff-only origin develop
git fetch --tags
git status --short
git tag --sort=-version:refname
git log --first-parent --oneline v0.3.0..HEAD
git switch -c release/v0.4.0
```

The `release/vX.Y.Z` branch name is required by the publication workflow. Do not use `release/X.Y.Z`.

## 2. Update version metadata

```bash
uv version 0.4.0
sed -i 's/version-0\.3\.0-blue/version-0.4.0-blue/' README.md
cd frontend
npm version 0.4.0 --no-git-tag-version
cd ..
```

These commands update `pyproject.toml`, `uv.lock`, `frontend/package.json` and `frontend/package-lock.json`. Update the version badge in `README.md` as well. Do not replace historical versions or unrelated dependency versions globally.

## 3. Update documentation

Add exactly one dated `## [0.4.0] - YYYY-MM-DD` section to `CHANGELOG.md`, using the intended publication date. Keep the `Unreleased` heading and historical entries. Move the relevant unreleased changes into the new section and update the comparison links:

```markdown
[Unreleased]: https://github.com/cmartinferrer/cmf-dev-studio/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/cmartinferrer/cmf-dev-studio/compare/v0.3.0...v0.4.0
```

Review the README for new features, usage, architecture and limitations. Release notes are extracted from the version's changelog section automatically.

## 4. Validate

```bash
uv lock --check
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -q -m "not integration"
cd frontend
npm ci
npm run build
npm audit --audit-level=high
cd ..
```

Run native integration tests when the required tools are available (`uv run --locked pytest -q -m integration`). Perform relevant manual end-to-end checks with Gemini when releasing agent or UI changes.

Validate release metadata and preview the exact notes:

```bash
uv run --locked python scripts/release.py release/v0.4.0 --notes /tmp/release-notes-0.4.0.md
cat /tmp/release-notes-0.4.0.md
git diff --check
git status --short
git diff --stat
```

The script must print `0.4.0`. It checks the branch name, backend and frontend versions, both lockfiles and the matching nonempty changelog section.

## 5. Commit and push

```bash
git add CHANGELOG.md README.md pyproject.toml uv.lock
git add frontend/package.json frontend/package-lock.json
git diff --cached --check
git diff --cached --stat
git status --short
git commit -m "chore: prepare release v0.4.0"
git push -u origin release/v0.4.0
```

Stage `RELEASING.md` explicitly if it has changed. Include only intended release preparation files.

## 6. Open and merge the release pull request

Open a GitHub pull request with base `main` and compare `release/v0.4.0`. Summarize the release and included feature PRs. Wait for required checks and approvals, then merge according to the repository's branch protection rules. Prefer a merge commit to preserve development history where permitted.

Do not merge the release branch into `develop` instead of `main`, and do not manually create the tag or GitHub Release. The publication workflow only runs for merged same-repository `release/v*` pull requests targeting `main`.

## 7. Verify automatic publication

In GitHub Actions, check the **Release** workflow triggered by the merge. It validates the merged commit, creates the tag pointing to that commit and publishes a stable GitHub Release using the extracted changelog notes.

Verify the tag and release at <https://github.com/cmartinferrer/cmf-dev-studio/releases>.

```bash
git fetch origin --tags
git show --no-patch v0.4.0
```

If publication fails, inspect the workflow logs and rerun the failed workflow after resolving the cause. The workflow can reuse a tag already pointing to the same merge commit. A tag pointing to a different commit is an error; do not move or delete published tags to bypass it.

## 8. Verify automatic synchronization

After publication, the `sync-develop` job creates a release-specific `sync/release-vX.Y.Z` branch and opens a pull request targeting `develop`. It merges the published tag into the current development history, then requests auto-merge with a merge commit. Required checks and branch rules remain enforced. No direct push to `develop` is performed.

If `develop` already contains the release commit, the job exits without creating a PR. A retry reuses the existing synchronization branch and open PR. If conflicts occur, the job fails without forcing changes; resolve them on the synchronization branch or prepare a manual PR. If `develop` advances while checks are running, rerun synchronization to update the branch. Check the PR and its required checks before considering synchronization complete.

To retry without publishing a new release, run the **Release** workflow manually on `main` and enter the existing stable tag (for example `v0.4.0`). This runs synchronization only. The workflow must already be present on `main`.

After the synchronization PR merges, update local branches:

```bash
git switch main
git pull --ff-only origin main
git switch develop
git pull --ff-only origin develop
```

Delete temporary branches only after their changes are merged and the release is verified.

## Release automation setup

Enable **Allow auto-merge** in repository settings. Install the dedicated GitHub App only on this repository, with Contents and Pull requests read/write permissions (and automatic Metadata read access). If GitHub rejects a synchronization because it introduces new workflow file contents, resolve that synchronization manually or review whether the additional Workflows write permission is justified. Do not grant branch protection bypass.

Configure the repository Actions variable `RELEASE_APP_ID` and secret `RELEASE_APP_PRIVATE_KEY` with the App ID and PEM private key respectively. Never commit the private key. The workflow uses a temporary installation token to trigger normal PR checks. Only checks configured as required block auto-merge; configure additional required checks separately if desired.
