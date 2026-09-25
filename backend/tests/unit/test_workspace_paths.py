import pytest

from app.workspace.paths import InvalidPathError, normalize_path


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("src/api.py", "src/api.py"),
        ("./src//api.py", "src/api.py"),
        ("src\\\\api.py", "src/api.py"),
        ("README.md", "README.md"),
        (".gitignore", ".gitignore"),
        ("Dockerfile", "Dockerfile"),
    ],
)
def test_valid_paths(raw, expected) -> None:
    assert normalize_path(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "../etc/passwd.txt",  # fugir do projeto
        "src/../../x.py",
        "/etc/passwd.txt",  # absoluto
        "C:/Windows/x.py",
        ".env",  # segredos
        ".git/config.txt",
        "virus.exe",  # extensão não permitida
        "src/ficheiro com espaços.py",
        "",
        "a/" * 10 + "x.py",  # demasiado profundo
    ],
)
def test_rejected_paths(raw) -> None:
    with pytest.raises(InvalidPathError):
        normalize_path(raw)
