import time
import unittest

from sketchstack import Candidate, Dependency, Result, parse_version, resolve

STACK = "web"


def cand(name, major, deps=(), stack=STACK):
    return Candidate(name, stack, (major, 0, 0), tuple(deps))


def dep(name, lower, upper=None):
    upper = upper if upper is not None else (lower[0] + 1, 0, 0)
    return Dependency(name, lower, upper)


class TestBasic(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))
        with self.assertRaises(ValueError):
            parse_version("1.2")
        with self.assertRaises(ValueError):
            parse_version("1.2.3-rc1")

    def test_empty_roots(self):
        r = resolve([], STACK, [])
        self.assertTrue(r.ok)
        self.assertEqual(r.locked, {})

    def test_single_root_picks_latest(self):
        catalog = [cand("A", 1), cand("A", 2)]
        r = resolve(catalog, STACK, ["A"])
        self.assertTrue(r.ok)
        self.assertEqual(r.locked, {"A": (2, 0, 0)})

    def test_other_stack_cannot_fill(self):
        catalog = [cand("A", 1, deps=[dep("X", (1, 0, 0))]),
                   cand("X", 1, stack="other")]
        r = resolve(catalog, STACK, ["A"])
        self.assertFalse(r.ok)

    def test_missing_root_is_failure(self):
        r = resolve([cand("A", 1)], STACK, ["A", "ZZZ"])
        self.assertFalse(r.ok)
        self.assertIn("ZZZ", r.reason)

    def test_duplicate_roots_rejected(self):
        with self.assertRaises(ValueError):
            resolve([], STACK, ["A", "A"])

    def test_dependency_range_excludes_upper(self):
        catalog = [
            cand("A", 1, deps=[dep("X", (1, 0, 0), (2, 0, 0))]),
            cand("X", 1), cand("X", 2),
        ]
        r = resolve(catalog, STACK, ["A"])
        self.assertTrue(r.ok)
        self.assertEqual(r.locked["X"], (1, 0, 0))


class TestRootPriority(unittest.TestCase):
    """A2->X1, A1->X2; B2->X2, B1->X1。根顺序决定谁保新版本。"""

    def setUp(self):
        self.catalog = [
            cand("A", 2, deps=[dep("X", (1, 0, 0), (2, 0, 0))]),
            cand("A", 1, deps=[dep("X", (2, 0, 0), (3, 0, 0))]),
            cand("B", 2, deps=[dep("X", (2, 0, 0), (3, 0, 0))]),
            cand("B", 1, deps=[dep("X", (1, 0, 0), (2, 0, 0))]),
            cand("X", 1), cand("X", 2),
        ]

    def test_a_first(self):
        r = resolve(self.catalog, STACK, ["A", "B"])
        self.assertTrue(r.ok)
        self.assertEqual(r.locked, {"A": (2, 0, 0), "B": (1, 0, 0), "X": (1, 0, 0)})

    def test_b_first(self):
        r = resolve(self.catalog, STACK, ["B", "A"])
        self.assertTrue(r.ok)
        self.assertEqual(r.locked, {"B": (2, 0, 0), "A": (1, 0, 0), "X": (2, 0, 0)})

    def test_no_stale_residue(self):
        # 锁定结果恰好是可达闭包，不含回退前引入的版本
        r = resolve(self.catalog, STACK, ["A", "B"])
        self.assertEqual(set(r.locked), {"A", "B", "X"})
        versions = list(r.locked.values())
        self.assertEqual(len(versions), len(set((n, v) for n, v in r.locked.items())))


class TestCycles(unittest.TestCase):
    def test_compatible_cycle_succeeds(self):
        catalog = [
            cand("P", 1, deps=[dep("Q", (1, 0, 0), (2, 0, 0))]),
            cand("Q", 1, deps=[dep("P", (1, 0, 0), (2, 0, 0))]),
        ]
        r = resolve(catalog, STACK, ["P"])
        self.assertTrue(r.ok)
        self.assertEqual(r.locked, {"P": (1, 0, 0), "Q": (1, 0, 0)})

    def test_contradictory_cycle_fails(self):
        catalog = [
            cand("P", 1, deps=[dep("Q", (2, 0, 0), (3, 0, 0))]),
            cand("Q", 2, deps=[dep("P", (2, 0, 0), (3, 0, 0))]),
        ]
        r = resolve(catalog, STACK, ["P"])
        self.assertFalse(r.ok)

    def test_unreachable_contradiction_does_not_pollute(self):
        catalog = [
            cand("P", 1, deps=[dep("Q", (2, 0, 0), (3, 0, 0))]),
            cand("Q", 2, deps=[dep("P", (2, 0, 0), (3, 0, 0))]),
            cand("R", 1, deps=[dep("S", (1, 0, 0), (2, 0, 0))]),
            cand("S", 1),
        ]
        r = resolve(catalog, STACK, ["R"])
        self.assertTrue(r.ok)
        self.assertEqual(r.locked, {"R": (1, 0, 0), "S": (1, 0, 0)})


class TestTwentyRoots(unittest.TestCase):
    def test_forced_downgrade_within_5s(self):
        catalog = []
        # 前 19 个根：各 4 版；较新 3 版经独有双层片段依赖 Shared 2.0.0；最旧版依赖 Shared 1.0.0
        for i in range(19):
            f1, f2 = f"F{i}a", f"F{i}b"
            for major in (2, 3, 4):
                catalog.append(cand(f"R{i}", major,
                                    deps=[dep(f1, (1, 0, 0), (2, 0, 0))]))
            catalog.append(cand(f"R{i}", 1, deps=[dep("Shared", (1, 0, 0), (2, 0, 0))]))
            catalog.append(cand(f1, 1, deps=[dep(f2, (1, 0, 0), (2, 0, 0))]))
            catalog.append(cand(f2, 1, deps=[dep("Shared", (2, 0, 0), (3, 0, 0))]))
        # 第 20 个根：只有一版，固定依赖 Shared 1.0.0
        catalog.append(cand("R19", 1, deps=[dep("Shared", (1, 0, 0), (2, 0, 0))]))
        catalog.append(cand("Shared", 1))
        catalog.append(cand("Shared", 2))
        # 无关候选补至 500（复用 40 个无关组件名，版本递增，不超出 100 个组件名上限）
        versions = {}

        def next_version(name):
            versions[name] = versions.get(name, 0) + 1
            return (versions[name], 0, 0)

        pad = 0
        while len(catalog) < 499:
            a, b = f"Pad{pad}", f"PadDep{pad}"
            va, vb = next_version(a), next_version(b)
            catalog.append(Candidate(a, STACK, va,
                                     (Dependency(b, vb, (vb[0] + 1, 0, 0)),)))
            catalog.append(Candidate(b, STACK, vb))
            pad = (pad + 1) % 20
        while len(catalog) < 500:
            name = "PadSolo"
            catalog.append(Candidate(name, STACK, next_version(name)))
        self.assertEqual(len(catalog), 500)

        roots = [f"R{i}" for i in range(20)]
        start = time.monotonic()
        r = resolve(catalog, STACK, roots)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 5.0)
        self.assertTrue(r.ok, r.reason)
        # 唯一合法根版本向量：全部取最旧版
        for root in roots:
            self.assertEqual(r.locked[root], (1, 0, 0), root)
        self.assertEqual(r.locked["Shared"], (1, 0, 0))
        # 只被高版本引入的片段不得残留
        for i in range(19):
            self.assertNotIn(f"F{i}a", r.locked)
            self.assertNotIn(f"F{i}b", r.locked)
        self.assertEqual(set(r.locked), set(roots) | {"Shared"})


if __name__ == "__main__":
    unittest.main()
