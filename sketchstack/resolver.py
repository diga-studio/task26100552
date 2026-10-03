"""模板联合选版器：resolve(catalog, stack, roots)。

求解策略：
1. 只索引目标技术栈的候选，其他技术栈不参与求解。
2. 按 roots 顺序逐个固定根组件：对每个根从高到低尝试其版本，
   用完整回溯搜索判定“固定该版本后整体是否可行”，
   第一个可行的版本即被保留——这保证根版本向量字典序最大。
3. 回溯搜索只从根出发沿依赖按需展开，不物化笛卡尔积，
   不设置搜索次数/深度/耗时上限；循环依赖通过“已分配即检查”自然处理。
4. 最终锁定清单 = 从根出发沿所选版本依赖可达的组件集合，
   搜索过程中被回退掉的组件不会残留。
"""

from __future__ import annotations

from collections.abc import Iterable

from .model import Candidate, LockResult
from .version import Version


def resolve(
    catalog: Iterable[Candidate],
    stack: str,
    roots: list[str],
) -> LockResult:
    """从目录中为一组根组件选出版本，返回锁定清单或无解结果。"""
    by_name: dict[str, list[Candidate]] = {}
    for cand in catalog:
        if cand.stack != stack:
            continue
        versions = by_name.setdefault(cand.name, [])
        if all(existing.version != cand.version for existing in versions):
            versions.append(cand)
    for versions in by_name.values():
        versions.sort(key=lambda cand: cand.version, reverse=True)

    for root in roots:
        if root not in by_name:
            return LockResult(
                ok=False,
                stack=stack,
                reason=f"根组件 {root!r} 在技术栈 {stack!r} 中没有任何候选",
            )

    if not roots:
        return LockResult(ok=True, stack=stack)

    fixed: dict[str, Candidate] = {}
    solution: dict[str, Candidate] | None = None
    for root in roots:
        advanced = False
        for cand in by_name[root]:
            trial = dict(fixed)
            trial[root] = cand
            solution = _search(trial, roots, by_name)
            if solution is not None:
                fixed[root] = cand
                advanced = True
                break
        if not advanced:
            return LockResult(
                ok=False,
                stack=stack,
                reason=(
                    f"根组件 {root!r} 的任何版本都无法与已固定的根版本共存"
                ),
            )

    assert solution is not None
    reachable = _reachable_closure(roots, solution)
    pins: dict[str, Version] = {
        name: solution[name].version for name in sorted(reachable)
    }
    return LockResult(
        ok=True,
        stack=stack,
        pins=pins,
        root_versions=tuple(solution[root].version for root in roots),
    )


def _search(
    assignment: dict[str, Candidate],
    roots: list[str],
    by_name: dict[str, list[Candidate]],
) -> dict[str, Candidate] | None:
    """完整回溯搜索：返回一个满足全部依赖区间的分配，或 None（无解）。

    每次调用从当前分配重算待分配集合，挑候选数最少的组件，
    按版本从高到低尝试；失败则撤销分配并尝试下一个版本。
    """
    pending: set[str] = set()
    for root in roots:
        if root not in assignment:
            pending.add(root)
    for cand in assignment.values():
        for dep in cand.deps:
            if dep.name not in assignment:
                pending.add(dep.name)

    if not pending:
        return assignment

    name = min(pending, key=lambda n: (len(by_name.get(n, ())), n))
    candidates = by_name.get(name)
    if not candidates:
        return None
    for cand in candidates:
        if not _consistent(cand, assignment):
            continue
        assignment[name] = cand
        result = _search(assignment, roots, by_name)
        if result is not None:
            return result
        del assignment[name]
    return None


def _consistent(cand: Candidate, assignment: dict[str, Candidate]) -> bool:
    """检查候选与当前分配双向一致：它的依赖、以及别人对它的依赖。"""
    for dep in cand.deps:
        if dep.name == cand.name:
            if not dep.accepts(cand.version):
                return False
            continue
        other = assignment.get(dep.name)
        if other is not None and not dep.accepts(other.version):
            return False
    for other in assignment.values():
        for dep in other.deps:
            if dep.name == cand.name and not dep.accepts(cand.version):
                return False
    return True


def _reachable_closure(
    roots: list[str],
    solution: dict[str, Candidate],
) -> set[str]:
    """从根出发沿所选版本的依赖可达的全部组件。"""
    seen: set[str] = set()
    queue = list(roots)
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        cand = solution.get(name)
        if cand is not None:
            queue.extend(dep.name for dep in cand.deps)
    return seen
