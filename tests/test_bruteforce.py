"""与暴力枚举对拍：小规模随机目录下，resolve 必须返回字典序最大的根版本向量。"""
import itertools
import random
import unittest

from sketchstack import Candidate, Dependency, resolve

STACK = "web"


def brute_force(catalog, stack, roots):
    """枚举所有 组件名->版本 赋值，返回 (最优根向量, 对应锁定) 或 None。"""
    by_name = {}
    deps_of = {}
    for c in catalog:
        if c.stack != stack:
            continue
        by_name.setdefault(c.name, set()).add(c.version)
        deps_of[(c.name, c.version)] = c.dependencies
    names = sorted(by_name)
    best = None
    for combo in itertools.product(*(sorted(by_name[n]) for n in names)):
        assign = dict(zip(names, combo))
        # 从根出发沿所选版本的依赖求可达闭包，并校验区间
        locked = {}
        queue = list(roots)
        valid = True
        while queue and valid:
            n = queue.pop()
            if n in locked:
                continue
            if n not in assign:
                valid = False
                break
            v = assign[n]
            locked[n] = v
            for d in deps_of.get((n, v), ()):
                if d.name not in assign:
                    valid = False
                    break
                dv = assign[d.name]
                if not (d.lower <= dv and (d.upper is None or dv < d.upper)):
                    valid = False
                    break
                queue.append(d.name)
        if not valid:
            continue
        vector = tuple(locked[r] for r in roots)
        if best is None or vector > best[0]:
            best = (vector, locked)
    return best


def check_lock(catalog, stack, roots, locked):
    """校验 locked 恰好是根沿所选版本的依赖可达闭包，且全部区间满足。"""
    deps_of = {(c.name, c.version): c.dependencies for c in catalog if c.stack == stack}
    seen = {}
    queue = list(roots)
    while queue:
        n = queue.pop()
        if n in seen:
            continue
        assert n in locked, f"{n} 可达但未锁定"
        v = locked[n]
        seen[n] = v
        for d in deps_of.get((n, v), ()):
            assert d.name in locked, f"{d.name} 是 {n} 的依赖但未锁定"
            dv = locked[d.name]
            assert d.lower <= dv and (d.upper is None or dv < d.upper), \
                f"{n}={v} 对 {d.name} 的区间 [{d.lower},{d.upper}) 不满足，实际 {dv}"
            queue.append(d.name)
    assert set(locked) == set(seen), f"锁定结果含不可达残留: {set(locked) - set(seen)}"


def random_catalog(rng, n_names=6, max_versions=2):
    names = [f"C{i}" for i in range(n_names)]
    catalog = []
    for name in names:
        for major in range(1, rng.randint(1, max_versions) + 1):
            deps = []
            for other in names:
                if other != name and rng.random() < 0.3:
                    lo = (rng.randint(1, max_versions), 0, 0)
                    hi = (lo[0] + rng.randint(1, 2), 0, 0)
                    deps.append(Dependency(other, lo, hi))
            catalog.append(Candidate(name, STACK, (major, 0, 0), tuple(deps)))
    return catalog, names


class TestBruteForce(unittest.TestCase):
    def test_random_against_brute_force(self):
        rng = random.Random(20261005)
        for trial in range(300):
            catalog, names = random_catalog(rng)
            roots = rng.sample(names, rng.randint(1, min(3, len(names))))
            expected = brute_force(catalog, STACK, roots)
            result = resolve(catalog, STACK, roots)
            if expected is None:
                self.assertFalse(result.ok, f"trial {trial}: 应为无解 {roots}")
            else:
                vector, _ = expected
                self.assertTrue(result.ok, f"trial {trial}: 应有解 {roots}")
                got = tuple(result.locked[r] for r in roots)
                self.assertEqual(got, vector, f"trial {trial}: 根向量不是字典序最大 {roots}")
                check_lock(catalog, STACK, roots, result.locked)


if __name__ == "__main__":
    unittest.main()
