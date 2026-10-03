"""目录与锁定结果的数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .version import Version


@dataclass(frozen=True)
class Dependency:
    """一条必需依赖：组件名 + 版本区间 [lower, upper)。"""

    name: str
    lower: Version
    upper: Version

    def accepts(self, version: Version) -> bool:
        """判断给定版本是否落在区间 [lower, upper) 内。"""
        return self.lower <= version < self.upper


@dataclass(frozen=True)
class Candidate:
    """一个已发布的模板候选：组件名、技术栈、版本、依赖清单。"""

    name: str
    stack: str
    version: Version
    deps: tuple[Dependency, ...] = ()


@dataclass(frozen=True)
class LockResult:
    """锁定结果。ok=False 时表示无解，reason 给出原因。"""

    ok: bool
    stack: str
    pins: dict[str, Version] = field(default_factory=dict)
    root_versions: tuple[Version, ...] = ()
    reason: str | None = None
