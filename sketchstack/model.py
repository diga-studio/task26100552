"""数据模型：模板候选、依赖与锁定结果。"""
from __future__ import annotations

from dataclasses import dataclass, field

Version = tuple[int, int, int]


def parse_version(text: str) -> Version:
    """把 "1.2.3" 形式的字符串解析为 (1, 2, 3)。"""
    parts = text.split(".")
    if len(parts) != 3:
        raise ValueError(f"版本号必须为主.次.修订 三段: {text!r}")
    nums = tuple(int(p) for p in parts)
    if any(n < 0 for n in nums):
        raise ValueError(f"版本号不允许负数: {text!r}")
    return nums  # type: ignore[return-value]


@dataclass(frozen=True)
class Dependency:
    """对另一组件的版本区间依赖，[lower, upper)，upper 为 None 表示无上界。"""
    name: str
    lower: Version
    upper: Version | None = None


@dataclass(frozen=True)
class Candidate:
    """一个已发布的模板候选：组件名 + 技术栈 + 版本 + 依赖清单。"""
    name: str
    stack: str
    version: Version
    dependencies: tuple[Dependency, ...] = ()


@dataclass
class Result:
    """求解结果。ok 为 True 时 locked 给出 组件名 -> 版本 的锁定清单。"""
    ok: bool
    locked: dict[str, Version] | None = None
    reason: str | None = None
