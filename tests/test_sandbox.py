from pathlib import Path

import pytest

from routemate.errors import SandboxViolation
from routemate.sandbox import MAX_CONTENT_BYTES, write_text_safely


def test_writes_utf8_text_inside_sandbox(tmp_path: Path) -> None:
    result = write_text_safely("行程/北京天气.md", "晴，15℃", tmp_path)

    assert result.relative_path == "行程/北京天气.md"
    assert (tmp_path / "行程" / "北京天气.md").read_text(encoding="utf-8") == "晴，15℃"
    assert result.bytes_written == len("晴，15℃".encode())


@pytest.mark.parametrize(
    "path",
    [
        "../escape.txt",
        "sub/../../escape.txt",
        "C:/Windows/escape.txt",
        "/tmp/escape.txt",
        "note.exe",
        "CON.txt",
    ],
)
def test_rejects_unsafe_paths(tmp_path: Path, path: str) -> None:
    with pytest.raises(SandboxViolation):
        write_text_safely(path, "blocked", tmp_path)


def test_rejects_oversized_content(tmp_path: Path) -> None:
    with pytest.raises(SandboxViolation, match="不能超过"):
        write_text_safely("large.txt", "x" * (MAX_CONTENT_BYTES + 1), tmp_path)

