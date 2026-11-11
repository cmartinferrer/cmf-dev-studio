# v3.4 — Workspace orchestration hardening (preview)

## Changes
- Repository patch generation uses a language-neutral prompt and detects languages from file names.
- Expanded safe text workspace snapshot paths for Java, Kotlin, Gradle, Maven, TypeScript, Go, Rust, Swift, etc. Existing size, symlink and sensitive-path restrictions remain.
- Validates generated operations *before* touching the isolated workspace. Retries invalid JSON, CREATE-on-existing and unauthorized operations up to three times. No permission is granted automatically.
- The chat shows actionable guidance and a Context shortcut for missing existing-file approval.
- Prevents non-Python proposals from being falsely marked as passing the Python-only Docker pytest runner. Java/Kotlin and other language-specific verification are NOT implemented yet.
- Added tests for language detection, safe paths and operation validation.

## Important limits
- Existing-file contents still require explicit Context approval. File inventory (paths only) does not authorize reading file contents.
- The original Analyst/Developer/Tester mission workflow remains Python-specific and is not yet migrated to a multi-language execution contract.
- The Python-only Docker runner and approval gate remain unchanged for Python projects. A non-Python test runner must be implemented before safe apply can be enabled for those projects.
- The repair loop retries the LLM; it does not auto-convert CREATE to MODIFY, which would bypass content authorization.

## Validation in build environment
- 175 Python unit tests passed excluding two modules requiring unavailable google-genai; 3 integration tests deselected.
- Frontend build not run because npm packages are unavailable in this environment.
