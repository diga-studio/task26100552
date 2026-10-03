"""语义化版本（仅主/次/修订三个非负整数）。"""

from __future__ import annotations

Version = tuple[int, int, int]


def parse_version(text: str) -> Version:
    """把 "1.2.3" 形式的字符串解析为 Version。

    只接受三个非负整数，不支持预发布或构建元数据。
    """
    parts = text.split(".")
    if len(parts) != 3:
        raise ValueError(f"版本必须形如 <major>.<minor>.<patch>: {text!r}")
    numbers: list[int] = []
    for part in parts:
        if not part.isdigit():
            raise ValueError(f"版本段必须是非负整数: {text!r}")
        numbers.append(int(part))
    return (numbers[0], numbers[1], numbers[2])


def format_version(version: Version) -> str:
    """把 Version 格式化为 "1.2.3" 形式。"""
    major, minor, patch = version
    return f"{major}.{minor}.{patch}"
