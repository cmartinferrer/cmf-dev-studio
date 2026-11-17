# Changelog

All notable changes to CMF Dev Studio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-11-17

### Added

- Per-project Python environment management, including virtual environment creation with uv and selection of existing interpreters.
- Per-project JDK detection, selection and persistence for Java and Kotlin projects.
- Python interpreter and JDK controls in the workspace status bar.
- Isolated Python test environments using the selected project interpreter and declared dependencies.
- Maven and Gradle Wrapper support, prioritizing project wrappers over globally installed build tools.
- Chat-driven Python dependency preparation and JVM project compilation and testing, with explicit user approval.
- Integrated editor execution for Python scripts, Java and Kotlin applications, and supported JVM test classes.
- Run, Stop and Run again actions, execution status, terminal output and process exit codes.
- Automated regression tests for environment management, terminal integration, project runners, dependency preparation and editor execution.

### Changed

- Integrated project-specific Python and JDK environments into the local terminal and multi-agent test workflow.
- Improved terminal font fallback support for Powerline glyphs.
- Updated the README to document project environments, dependency preparation, editor execution and current limitations.

### Fixed

- Prevented terminals from inheriting the Studio Python virtual environment when no project interpreter is selected.
- Preserved selected project environments during shell initialization without modifying the user's global shell configuration.

## [0.2.1] - 2026-11-17

### Changed

- Resolve the API version dynamically from Python package metadata.
- Resolve the frontend version dynamically from package.json.

### Fixed

- Correct the API version mismatch introduced in v0.2.0.

### Added

- Regression test to ensure the API version matches the installed package version.

## [0.2.0] - 2026-11-16

### Added

- Conversational AI chat with inline approvals, persistent conversation history and proposal repair actions.
- Automatic active-file context, manual context selection and context-aware retries.
- Programming language icons, editable project language and a workspace status bar.
- Contextual project, file and folder management actions.
- Folder creation, drag and drop, multi-selection, bulk operations and file explorer clipboard support.
- Automatic numbering of duplicate file and folder names.
- Ruff linting and formatting checks in local development and continuous integration.

### Changed

- Replaced Docker-based project test execution with explicitly approved native execution for Python, Maven and Gradle projects.
- Improved agent requirements, acceptance criteria, functional review and generated test quality.
- Improved test failure classification, bounded repair attempts and approval handling for revised proposals.
- Updated project documentation to reflect the current IDE and execution workflows.
- Updated FastAPI to 0.162.5, Vite to 8.3.8, Lucide React to 1.72.0 and xterm.js to 6.0.0.

### Fixed

- Prevented repeated execution of unchanged failed proposals.
- Improved conversational retry behavior and context preservation.
- Resolved the Starlette HTTPX deprecation warning by adopting HTTPX2 for tests.
- Added a narrowly scoped Gitleaks exception for a synthetic test credential.

### Removed

- Docker-based project runners and the obsolete Docker integration CI check.

## [0.1.0]

### Added

- Initial alpha version of CMF Dev Studio, a local-first browser-based development environment.
- Integrated Monaco editor, project registry, file explorer and local terminal.
- Language-independent orchestration of Analyst, Developer and Tester agents using Gemini.
- Repository-level proposals, context authorization, test execution and explicit change approval.
- Python, Java and Kotlin reference projects and runner integration tests.
- SQLite persistence for project and proposal data.
- GitHub Actions CI, dependency security auditing and secret scanning.

[Unreleased]: https://github.com/cmartinferrer/cmf-dev-studio/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/cmartinferrer/cmf-dev-studio/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/cmartinferrer/cmf-dev-studio/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/cmartinferrer/cmf-dev-studio/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/cmartinferrer/cmf-dev-studio/releases/tag/v0.1.0