> Historical record: superseded by the single-orchestrator architecture in README.md.

# V4 stabilization — 2026-11-12

Based on the user's uncommitted ZIP 20261112-064636. Preserves the working Docker mktemp and TypeScript fixes. No files need to be deleted.

- Python AST validation of generated operations before writing; bounded regeneration.
- Tester receives approved baseline and diffs, is instructed to preserve unrelated tests, and must approve every revised patch. Persistent review failures stop safely.
- Repair receives previous generated patch and test feedback; infrastructure errors do not trigger code repair. Runner is reselected after repairs.
- Test/apply serialized in the current backend process; tested digest invalidated before retest and checked across execution. Errors cannot leave a running proposal eligible for application.
- Context approval checked against snapshot bytes; missing context errors expose inline selection and restore the request. No automatic transmission of project contents. Context approval is still manual.
- Auto-test scheduled once per new proposal; context list refreshed when opened.

Validation: 194 passed, 3 integration tests deselected, three modules excluded (test_cli.py, test_gemini_client.py, test_repository_v11.py; google-genai unavailable). Python compileall and TypeScript syntax transpilation passed. Full npm build unavailable because npm cache lacks dependencies. Docker and live Gemini not available. Java/Kotlin real runs remain unverified. The repair regression uses real local pytest in a temporary fixture and mocked LLM/Docker adapter, not a real container. No claim of exhaustive coverage or production readiness.

Install by copying source files from this ZIP over the exact current project, preserving .env and local data. Run pytest and npm build. Restart backend and frontend. Existing failed greeting proposal can be retried; if approval is stale or repair fails, approve app/main.py, tests/test_main.py, pyproject.toml and submit a new greeting request. Review diffs before applying. Do not commit until real workflow validation.
