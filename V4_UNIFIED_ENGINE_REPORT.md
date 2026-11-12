# Multi-Agent Studio v4 — unified engine integration report

## Architecture

- `unified_engine.py` is the shared role coordinator. Legacy `Orchestrator.run()` delegates to `UnifiedEngine.run_mission()`. Repository proposals call `UnifiedEngine.plan_patch()`, `generate_patch()`, and `review_patch()`.
- Analyst produces independent requirements and acceptance criteria. Developer proposes validated structured operations. Tester reviews them. Failed isolated tests can trigger bounded developer repairs when a structured acceptance plan is available.
- `WorkspaceService` maintains separate snapshots, approved-file permissions, diffs, tests, and explicit apply confirmation. Approved files are not automatically expanded on retries.
- Java/Kotlin source prompts no longer force Python. Existing standalone mission execution retains a Python default for compatibility; IDE repository workflows select the build runner by manifest.
- Chat now offers inline context review/approval and shows role progress and acceptance criteria. Context counts show selectable candidates rather than a misleading total.

## Runner commands

Build the Docker images **on your development machine**:

```bash
# From repository root
docker build -f docker/project-test-runner.Dockerfile -t multi-agent-studio-project-tests:2.2 .
docker build -f docker/maven-test-runner.Dockerfile -t multi-agent-studio-maven-tests:4 .
docker build -f docker/gradle-test-runner.Dockerfile -t multi-agent-studio-gradle-tests:4 .
```

Java and Kotlin runners use offline Maven/Gradle for sandbox isolation. **A fresh image does not contain the dependencies of an arbitrary project**. They must be prepopulated in the image before real project tests can pass; missing dependencies are a known blocking limitation for arbitrary Java/Kotlin repositories. A test runner is never reported as successful when it cannot run.

## Validation performed in this environment

- `PYTHONPATH=src python -m pytest -q -m 'not integration' --ignore=tests/test_cli.py --ignore=tests/test_gemini_client.py`: **192 passed, 3 deselected**.
- Includes mocked end-to-end API flows for Java/Maven and Kotlin/Gradle (proposal, explicit context approval, isolated runner selection, apply).
- Python compilation passed. TypeScript/TSX syntax transpilation passed for edited frontend files.
- **Not verified:** full React build (npm dependencies unavailable), Gemini live calls, Docker integration (Docker daemon/CLI unavailable), real Maven/Gradle dependency resolution and test execution.

## Security invariants

- Only explicitly approved existing files can be modified or deleted by the AI.
- No project writes before successful isolated tests and explicit user confirmation.
- Test snapshots are integrity-hashed; any change after test invalidates application.
- Docker test execution is offline, unprivileged, read-only with resource limits and a temporary writable workspace.
- Unsupported projects and test failures are not reported as verified.

## Outstanding before production-ready v4

1. Validate actual Maven and Gradle project tests in Docker with real dependency caches.
2. Run `npm ci && npm run build` in an environment with npm registry access.
3. Run full suite with `google-genai` installed and Docker integration enabled.
4. Exercise live Gemini responses for Analyst/Developer/Tester and failure recovery.
5. Migrate the legacy standalone mission UI fully to repository-based proposals or explicitly retire it; both use the shared engine, but still have different output formats.
