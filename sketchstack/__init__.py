"""SketchStack 模板联合选版器。"""

from .model import Candidate, Dependency, LockResult
from .resolver import resolve
from .version import Version, format_version, parse_version

__all__ = [
    "Candidate",
    "Dependency",
    "LockResult",
    "Version",
    "format_version",
    "parse_version",
    "resolve",
]
