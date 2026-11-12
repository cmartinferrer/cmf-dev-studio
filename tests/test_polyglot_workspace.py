import pytest
from cmf_dev_studio.workspaces import (
    WorkspaceError, safe_path, detect_languages, validate_operations, build_workspace_prompt,
)


def test_polyglot_extensions_and_path_safety():
    for name in ('src/Main.java', 'src/App.kt', 'build.gradle.kts', 'pom.xml', 'src/app.ts'):
        assert safe_path(name)
    for name in ('../secrets.java', '.env', 'node_modules/a.js'):
        with pytest.raises(WorkspaceError):
            safe_path(name)


def test_language_detection():
    assert detect_languages({'src/App.kt': b'', 'pom.xml': b'', 'src/Main.java': b''}) == ['Java', 'Kotlin']
    assert 'Do not assume Python' in build_workspace_prompt('task', 'pom.xml', '', ['Java'])


def test_create_existing_requires_repair_and_permission():
    original = {'pyproject.toml': b'[project]', 'app/main.py': b'old'}
    with pytest.raises(WorkspaceError, match='already exists'):
        validate_operations([{'action':'create','path':'pyproject.toml','content':'new'}], original, set())
    with pytest.raises(WorkspaceError, match='Permission required'):
        validate_operations([{'action':'modify','path':'pyproject.toml','content':'new'}], original, set())
    validate_operations([{'action':'modify','path':'pyproject.toml','content':'new'}], original, {'pyproject.toml'})
    validate_operations([{'action':'create','path':'tests/test_new.py','content':'new'}], original, set())
