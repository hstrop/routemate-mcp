"""供文件 MCP 与离线演示共用的严格路径沙箱。"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .errors import SandboxViolation

ALLOWED_SUFFIXES = frozenset({".txt", ".md", ".json"})
MAX_CONTENT_BYTES = 100 * 1024
MAX_PATH_PARTS = 8
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True, slots=True)
class WriteResult:
    relative_path: str
    bytes_written: int


def _validate_parts(path: Path) -> None:
    if not path.parts or len(path.parts) > MAX_PATH_PARTS:
        raise SandboxViolation(f"文件路径层级必须在 1..{MAX_PATH_PARTS} 之间")
    for part in path.parts:
        if part in {"", ".", ".."}:
            raise SandboxViolation("文件路径不能包含空段、. 或 ..")
        if any(ord(character) < 32 for character in part):
            raise SandboxViolation("文件路径不能包含控制字符")
        if any(character in '<>:"|?*' for character in part):
            raise SandboxViolation("文件路径包含不安全字符")
        basename = part.rstrip(" .").split(".", maxsplit=1)[0].upper()
        if basename in _WINDOWS_RESERVED:
            raise SandboxViolation("文件路径包含系统保留名称")


def resolve_sandbox_path(relative_path: str, root: Path) -> tuple[Path, Path]:
    """解析并验证相对路径，返回 ``(根目录, 目标路径)``。"""

    if not isinstance(relative_path, str) or not relative_path.strip():
        raise SandboxViolation("文件名不能为空")
    if "\x00" in relative_path:
        raise SandboxViolation("文件名不能包含 NUL 字符")

    requested = Path(relative_path.strip())
    if requested.is_absolute() or requested.drive or requested.anchor:
        raise SandboxViolation("只允许沙箱内的相对路径")
    _validate_parts(requested)
    if requested.suffix.lower() not in ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_SUFFIXES))
        raise SandboxViolation(f"仅允许以下文本格式：{allowed}")

    resolved_root = root.expanduser().resolve(strict=False)
    resolved_target = (resolved_root / requested).resolve(strict=False)
    try:
        resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise SandboxViolation("目标路径越过了文件沙箱边界") from exc
    if resolved_target == resolved_root:
        raise SandboxViolation("目标必须是文件")
    return resolved_root, resolved_target


def write_text_safely(relative_path: str, content: str, root: Path) -> WriteResult:
    """在沙箱内原子写入 UTF-8 文本。"""

    if not isinstance(content, str):
        raise SandboxViolation("只允许写入文本内容")
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_CONTENT_BYTES:
        raise SandboxViolation(f"内容不能超过 {MAX_CONTENT_BYTES} 字节")

    resolved_root, target = resolve_sandbox_path(relative_path, root)
    resolved_root.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)

    # mkdir 后再次解析，避免既有符号链接把父目录带到沙箱外。
    resolved_parent = target.parent.resolve(strict=True)
    try:
        resolved_parent.relative_to(resolved_root.resolve(strict=True))
    except ValueError as exc:
        raise SandboxViolation("目标父目录越过了文件沙箱边界") from exc
    target = resolved_parent / target.name

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".routemate-", suffix=".tmp", dir=resolved_parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, target)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return WriteResult(
        relative_path=target.relative_to(resolved_root).as_posix(),
        bytes_written=len(encoded),
    )

