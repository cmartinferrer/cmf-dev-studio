> Historical record: superseded by the single-orchestrator architecture in README.md.

# JVM validation candidate

Repository review and test retry scheduling now live in unified_engine.py; WorkspaceService supplies persistence, snapshot and runner callbacks. The standalone mission API still uses its legacy single-source contract, so this is not yet a single repository pipeline for every entrypoint.

Build images from the repository root: `docker build -f docker/maven-test-runner.Dockerfile -t multi-agent-studio-maven-tests:4 .` and `docker build -f docker/gradle-test-runner.Dockerfile -t multi-agent-studio-gradle-tests:4 .`. The images prewarm dependencies for the bundled trusted examples only. Runtime stays offline; arbitrary dependencies are not supported unless preloaded. The Gradle and Maven caches are copied into writable temporary storage. Docker builds and actual JVM runs were not available in the authoring environment.

Register copies of examples/java-maven and examples/kotlin-gradle as existing projects, authorize source, test and build manifests, and request a subtract method with independent tests. Verify and approve explicitly. Keep the Python regression scenario. Frontend unchanged.
