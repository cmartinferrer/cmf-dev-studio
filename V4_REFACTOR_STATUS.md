> Historical record: superseded by the single-orchestrator architecture in README.md.

# Unified engine refactor — verification status

## Implemented
- `UnifiedEngine` owns Analyst → Developer → Tester → validation ordering and bounded retry decisions.
- Both legacy standalone missions and IDE workspace proposals call the same engine, using adapters for their different artifact types.
- IDE proposal generation asks the Analyst for acceptance criteria, Developer for structured file operations and Tester for independent behavioral tests, then validates operations and retries malformed/unsafe results without granting additional file permissions.
- Project runner selection recognizes Python/pytest, Maven, and Gradle projects. Docker commands use no network, limited resources and read-only source mounts. Maven and Gradle runners require their images to be built and dependencies to be cached offline.
- Repository context UI shows actual available files, selected count and the selection limit separately.

## Not completed — do not represent as production-ready
- Failed Docker tests in IDE proposals now trigger up to two bounded Developer repair attempts, restricted to the original proposal paths. The regeneration path is covered by deterministic tests but not a real Gemini/Docker end-to-end run.
- The legacy mission artifact remains a standalone Python code/test pair. It now uses the same `UnifiedEngine` as IDE proposals but does not yet produce repository patches or support JVM execution.
- Java/Kotlin runners require Docker image preparation and offline dependencies; no end-to-end JVM build was executed here.
- Context is still explicitly selected in a separate view, rather than proposed automatically by the IDE.
- Role-generated acceptance criteria are prompted but not independently machine-verified against requirements.
- JVM Docker images have not been built or exercised; the offline Maven/Gradle runners cannot resolve uncached dependencies.
- React build could not run here because the npm offline cache is incomplete.
- Full Python suite could not be collected because `google-genai` is absent from this environment. The remaining 181 tests passed.

## Build JVM runner images
```
docker build -f docker/maven-test-runner.Dockerfile -t multi-agent-studio-maven-tests:4 .
docker build -f docker/gradle-test-runner.Dockerfile -t multi-agent-studio-gradle-tests:4 .
```
