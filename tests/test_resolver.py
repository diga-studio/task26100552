"""SketchStack 选版器测试。"""

from __future__ import annotations

import time

import pytest

from sketchstack import (
    Candidate,
    Dependency,
    Version,
    format_version,
    parse_version,
    resolve,
)

STACK = "py"


def dep(name: str, lower: str, upper: str) -> Dependency:
    return Dependency(name=name, lower=parse_version(lower), upper=parse_version(upper))


def cand(name: str, version: str, deps=(), stack: str = STACK) -> Candidate:
    return Candidate(
        name=name,
        stack=stack,
        version=parse_version(version),
        deps=tuple(deps),
    )


def build_abx_catalog() -> list[Candidate]:
    return [
        cand("A", "2.0.0", [dep("X", "1.0.0", "2.0.0")]),
        cand("A", "1.0.0", [dep("X", "2.0.0", "3.0.0")]),
        cand("B", "2.0.0", [dep("X", "2.0.0", "3.0.0")]),
        cand("B", "1.0.0", [dep("X", "1.0.0", "2.0.0")]),
        cand("X", "1.0.0"),
        cand("X", "2.0.0"),
    ]


class TestVersion:
    def test_parse_and_format(self):
        assert parse_version("1.2.3") == (1, 2, 3)
        assert format_version((0, 10, 4)) == "0.10.4"

    @pytest.mark.parametrize("bad", ["1.2", "1.2.3.4", "1.2.x", "1.2.3-rc1", "-1.0.0", ""])
    def test_parse_rejects_bad_input(self, bad: str):
        with pytest.raises(ValueError):
            parse_version(bad)

    def test_ordering(self):
        assert (1, 0, 0) < (1, 0, 1) < (1, 1, 0) < (2, 0, 0)


class TestRootOrderPriority:
    def test_roots_ab(self):
        result = resolve(build_abx_catalog(), STACK, ["A", "B"])
        assert result.ok
        assert result.root_versions == ((2, 0, 0), (1, 0, 0))
        assert result.pins == {
            "A": (2, 0, 0),
            "B": (1, 0, 0),
            "X": (1, 0, 0),
        }

    def test_roots_ba(self):
        result = resolve(build_abx_catalog(), STACK, ["B", "A"])
        assert result.ok
        assert result.root_versions == ((2, 0, 0), (1, 0, 0))
        assert result.pins == {
            "B": (2, 0, 0),
            "A": (1, 0, 0),
            "X": (2, 0, 0),
        }

    def test_no_residue_from_backtracking(self):
        result = resolve(build_abx_catalog(), STACK, ["A", "B"])
        assert result.ok
        assert set(result.pins) == {"A", "B", "X"}
        assert result.pins["X"] == (1, 0, 0)


class TestCycles:
    def test_compatible_cycle_succeeds(self):
        catalog = [
            cand("P", "1.0.0", [dep("Q", "1.0.0", "2.0.0")]),
            cand("Q", "1.0.0", [dep("P", "1.0.0", "2.0.0")]),
        ]
        result = resolve(catalog, STACK, ["P"])
        assert result.ok
        assert result.pins == {"P": (1, 0, 0), "Q": (1, 0, 0)}

    def test_contradictory_cycle_unsolvable(self):
        catalog = [
            cand("P", "1.0.0", [dep("Q", "1.0.0", "2.0.0")]),
            cand("Q", "1.0.0", [dep("P", "2.0.0", "3.0.0")]),
        ]
        result = resolve(catalog, STACK, ["P"])
        assert not result.ok
        assert result.pins == {}
        assert result.reason

    def test_unreachable_contradictory_cycle_does_not_pollute(self):
        catalog = [
            cand("P", "1.0.0", [dep("Q", "1.0.0", "2.0.0")]),
            cand("Q", "1.0.0", [dep("P", "2.0.0", "3.0.0")]),
            cand("R", "1.0.0"),
            cand("R", "2.0.0"),
        ]
        result = resolve(catalog, STACK, ["R"])
        assert result.ok
        assert result.pins == {"R": (2, 0, 0)}


class TestStackIsolation:
    def test_empty_roots(self):
        result = resolve([cand("A", "1.0.0")], STACK, [])
        assert result.ok
        assert result.pins == {}
        assert result.root_versions == ()

    def test_other_stack_candidates_cannot_fill_in(self):
        catalog = [
            cand("A", "1.0.0", [dep("X", "1.0.0", "2.0.0")]),
            cand("X", "1.0.0", stack="node"),
        ]
        result = resolve(catalog, STACK, ["A"])
        assert not result.ok

    def test_root_missing_in_stack(self):
        result = resolve([cand("A", "1.0.0")], STACK, ["ZZZ"])
        assert not result.ok


class TestTwentyRootsScale:
    def _build_catalog(self) -> list[Candidate]:
        catalog: list[Candidate] = []
        for i in range(1, 20):
            root = f"R{i:02d}"
            frag_a = f"F{i:02d}_A"
            frag_b = f"F{i:02d}_B"
            for major in (4, 3, 2):
                catalog.append(
                    cand(root, f"{major}.0.0", [dep(frag_a, "1.0.0", "2.0.0")])
                )
            catalog.append(cand(root, "1.0.0", [dep("SHARED", "1.0.0", "2.0.0")]))
            catalog.append(cand(frag_a, "1.0.0", [dep(frag_b, "1.0.0", "2.0.0")]))
            catalog.append(cand(frag_b, "1.0.0", [dep("SHARED", "2.0.0", "3.0.0")]))
        catalog.append(cand("R20", "1.0.0", [dep("SHARED", "1.0.0", "2.0.0")]))
        catalog.append(cand("SHARED", "1.0.0"))
        catalog.append(cand("SHARED", "2.0.0"))
        filler = 0
        while len(catalog) < 500:
            filler += 1
            for major in (4, 3, 2, 1):
                if len(catalog) >= 500:
                    break
                catalog.append(
                    cand(f"FILLER{filler:03d}", f"{major}.0.0",
                         [dep("NOPE", "1.0.0", "2.0.0")])
                )
        assert len(catalog) == 500
        return catalog

    def test_unique_legal_root_vector_within_five_seconds(self):
        catalog = self._build_catalog()
        roots = [f"R{i:02d}" for i in range(1, 21)]
        start = time.monotonic()
        result = resolve(catalog, STACK, roots)
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"求解耗时 {elapsed:.2f}s 超过 5s"
        assert result.ok
        assert result.root_versions == ((1, 0, 0),) * 20
        assert result.pins["SHARED"] == (1, 0, 0)
        assert set(result.pins) == set(roots) | {"SHARED"}
        assert not any(name.startswith("F") and "_A" in name for name in result.pins)
        assert not any(name.startswith("F") and "_B" in name for name in result.pins)
