"""模板联合选版器。

算法：按 roots 顺序对根组件做决策（版本从大到小），依赖约束即时传播，
单例组件被强制赋值；冲突时记录责任决策集合做冲突导向回溯跳跃（CBJ）。
第一个可行解即字典序最大的根版本向量；搜索完备，无解判定不依赖任何次数/深度上限。
"""
from __future__ import annotations

from .model import Candidate, Dependency, Result, Version

MAX_CANDIDATES = 500
MAX_NAMES = 100
MAX_ROOTS = 20


class _Conflict(Exception):
    """传播中发现不可满足，vars 为需负责的决策组件名集合。"""

    def __init__(self, vars: frozenset[str]):
        super().__init__()
        self.vars = vars


def _check_version(v: object, what: str) -> Version:
    if (
        not isinstance(v, tuple)
        or len(v) != 3
        or any(not isinstance(n, int) or isinstance(n, bool) or n < 0 for n in v)
    ):
        raise ValueError(f"{what} 必须是三个非负整数组成的元组，得到 {v!r}")
    return v  # type: ignore[return-value]


def _in_range(v: Version, lo: Version, hi: Version | None) -> bool:
    return lo <= v and (hi is None or v < hi)


class _Solver:
    def __init__(self, catalog: list[Candidate], stack: str, roots: list[str]):
        self.roots = list(roots)
        # 只保留目标技术栈的候选；同名同版本去重。
        deps_of: dict[tuple[str, Version], tuple[Dependency, ...]] = {}
        for cand in catalog:
            if cand.stack != stack:
                continue
            deps_of.setdefault((cand.name, cand.version), cand.dependencies)
        self.deps_of = deps_of
        by_name: dict[str, list[Version]] = {}
        for name, version in deps_of:
            by_name.setdefault(name, []).append(version)
        self.by_name = {n: tuple(sorted(vs, reverse=True)) for n, vs in by_name.items()}

        # 可回溯状态
        self.assigned: dict[str, Version] = {}
        self.reason: dict[str, frozenset[str]] = {}
        self.allowed: dict[str, set[Version]] = {}
        self.blame: dict[str, set[str]] = {}
        self.trail: list[tuple] = []

    # ---- 传播 ----

    def _assign(self, name: str, version: Version, rsn: frozenset[str]) -> None:
        self.trail.append(("unassign", name))
        self.assigned[name] = version
        self.reason[name] = rsn
        for dep in self.deps_of.get((name, version), ()):
            self._add_constraint(name, dep)

    def _add_constraint(self, depender: str, dep: Dependency) -> None:
        name = dep.name
        old_allowed = self.allowed.get(name)
        old_blame = self.blame.get(name)
        self.trail.append(("restore_allowed", name, old_allowed, old_blame))
        base = old_allowed if old_allowed is not None else set(self.by_name.get(name, ()))
        new_blame = (old_blame if old_blame is not None else set()) | self.reason[depender]
        new_allowed = {v for v in base if _in_range(v, dep.lower, dep.upper)}
        self.allowed[name] = new_allowed
        self.blame[name] = new_blame
        current = self.assigned.get(name)
        if current is not None:
            if not _in_range(current, dep.lower, dep.upper):
                raise _Conflict(self.reason[depender] | self.reason[name])
            return
        if not new_allowed:
            raise _Conflict(frozenset(new_blame))
        if len(new_allowed) == 1:
            self._assign(name, next(iter(new_allowed)), frozenset(new_blame))

    # ---- 回溯 ----

    def _undo(self, mark: int) -> None:
        while len(self.trail) > mark:
            entry = self.trail.pop()
            if entry[0] == "unassign":
                del self.assigned[entry[1]]
                del self.reason[entry[1]]
            else:
                _, name, old_allowed, old_blame = entry
                if old_allowed is None:
                    del self.allowed[name]
                    del self.blame[name]
                else:
                    self.allowed[name] = old_allowed
                    self.blame[name] = old_blame

    # ---- 搜索 ----

    def _pick(self) -> str | None:
        for root in self.roots:
            if root not in self.assigned:
                return root
        best: str | None = None
        for name in self.allowed:
            if name in self.assigned:
                continue
            if best is None or len(self.allowed[name]) < len(self.allowed[best]):
                best = name
        return best

    def _domain(self, name: str) -> list[Version]:
        if name in self.allowed:
            return sorted(self.allowed[name], reverse=True)
        return list(self.by_name.get(name, ()))

    def _search(self) -> tuple[bool, frozenset[str] | None]:
        name = self._pick()
        if name is None:
            return True, None
        conf: frozenset[str] = frozenset({name})
        for version in self._domain(name):
            mark = len(self.trail)
            try:
                self._assign(name, version, frozenset({name}))
            except _Conflict as exc:
                conflict = exc.vars
            else:
                ok, conflict = self._search()
                if ok:
                    return True, None
            self._undo(mark)
            if name not in conflict:
                return False, conflict
            conf |= conflict - {name}
        return False, conf

    def solve(self) -> Result:
        ok, _ = self._search()
        if ok:
            return Result(ok=True, locked=dict(self.assigned))
        missing = [r for r in self.roots if r not in self.by_name]
        if missing:
            return Result(ok=False, reason=f"技术栈中不存在根组件候选: {missing}")
        return Result(ok=False, reason="依赖约束不可满足")


def resolve(catalog: list[Candidate], stack: str, roots: list[str]) -> Result:
    """为 roots 在指定技术栈中求联合锁定清单。

    返回 Result：ok=True 时 locked 为 组件名 -> 版本 的完整锁定；
    ok=False 表示无解，reason 给出简要说明。
    """
    if len(roots) != len(set(roots)):
        raise ValueError("roots 中的组件名必须互异")
    if len(roots) > MAX_ROOTS:
        raise ValueError(f"根组件数量超过上限 {MAX_ROOTS}")
    if len(catalog) > MAX_CANDIDATES:
        raise ValueError(f"目录候选数量超过上限 {MAX_CANDIDATES}")
    names = set()
    for cand in catalog:
        if not isinstance(cand, Candidate):
            raise TypeError(f"catalog 元素必须是 Candidate，得到 {type(cand)!r}")
        _check_version(cand.version, f"候选 {cand.name} 的版本")
        names.add(cand.name)
        for dep in cand.dependencies:
            _check_version(dep.lower, f"{cand.name} 依赖 {dep.name} 的下界")
            if dep.upper is not None:
                _check_version(dep.upper, f"{cand.name} 依赖 {dep.name} 的上界")
                if dep.upper <= dep.lower:
                    raise ValueError(f"{cand.name} 依赖 {dep.name} 的区间为空")
    if len(names) > MAX_NAMES:
        raise ValueError(f"组件名数量超过上限 {MAX_NAMES}")
    if not roots:
        return Result(ok=True, locked={})
    return _Solver(catalog, stack, roots).solve()
