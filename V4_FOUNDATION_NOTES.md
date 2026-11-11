# v4 — Unified Orchestration Foundation (incremental preview)

This is **not yet a fully unified multi-language agent engine**. It introduces shared workflow contracts while preserving the existing mission and workspace flows to avoid breaking the IDE.

## Implemented
- `workflow.py`: shared agent role enum, retry policy, conservative technology profile, and implementation-independent acceptance-test guidance.
- Both mission orchestrator and workspace proposal generator use the shared retry policy.
- Tester agent and workspace patch prompt receive acceptance guidance that discourages circular tests.
- Repository context explicitly permits known build manifests (`pyproject.toml`, `pom.xml`, `build.gradle[.kts]`, `package.json`, `Cargo.toml`, `go.mod`), while preserving credential scanning, file size limits and explicit user approval.
- Workspace test runner selects Python pytest only for Python-only projects; unsupported or mixed stacks fail closed rather than reporting false verification.
- Pytest success is determined by process exit code, not by matching the text 'passed'.
- New regression tests for manifest authorization, language adapter detection, shared retry policy and acceptance guidance.

## Not implemented yet
- A single execution graph routing both mission and repository patch requests through the same Analyst → Developer → Tester pipeline.
- Actual Java/Kotlin sandbox runners; technology identification does not equal test support.
- Automatic developer repair after Docker test failures for repository proposals.
- Automatic context approval (intentionally not granted without user consent).
- Frontend changes or Git support.

## Validation
- 59 selected tests passed in the container (Python path configured explicitly).
- Full suite not validated in this container because the installed environment lacks `google-genai` and is not the user's uv environment.
- Frontend not changed, build not executed here.

Run on your machine:
`uv run pytest -q -m "not integration"`
`cd frontend && npm run build`
