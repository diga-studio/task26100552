"""SketchStack 模板联合选版器。"""
from .model import Candidate, Dependency, Result, Version, parse_version
from .solver import resolve

__all__ = [
    "Candidate",
    "Dependency",
    "Result",
    "Version",
    "parse_version",
    "resolve",
]
