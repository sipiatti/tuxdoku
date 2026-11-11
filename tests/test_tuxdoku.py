import random

import pytest

from tuxdoku import puzzle as pz
from tuxdoku import rules
from tuxdoku.game import LevelState, Mark, Result
from tuxdoku.storage import Store


# ---------------------------------------------------------------- generator
@pytest.mark.parametrize("size", [5, 6, 7, 8, 9, 10])
def test_generated_puzzles_are_valid_and_unique(size):
    for seed in range(4 if size < 10 else 2):
        p = pz.generate(size, seed=seed)
        assert p.size == size
        assert pz.regions_are_contiguous(size, p.regions)
        assert sorted({v for row in p.regions for v in row}) == list(range(size))
        assert pz.is_valid_placement(size, p.regions, p.solution_cells())
        sols, _ = pz.solve(size, p.regions, limit=3)
        assert sols == [p.solution]


def test_generation_is_deterministic_per_seed():
    assert pz.generate(7, seed=42).to_dict() == pz.generate(7, seed=42).to_dict()


def test_random_placement_never_touches():
    rng = random.Random(1)
    for n in range(4, 11):
        for _ in range(20):
            sol = pz.random_placement(n, rng)
            assert sorted(sol) == list(range(n))
            assert all(abs(sol[r] - sol[r + 1]) > 1 for r in range(n - 1))


def test_round_trip_dict():
    p = pz.generate(6, seed=3)
    assert pz.Puzzle.from_dict(p.to_dict()) == p


# ---------------------------------------------------------- solver & rules
def test_adjacency_rule():
    assert pz.cells_touch((2, 2), (3, 3))   # diagonal
    assert pz.cells_touch((2, 2), (2, 3))
    assert not pz.cells_touch((2, 2), (4, 3))
    assert not pz.cells_touch((2, 2), (2, 2))


def test_solver_rejects_diagonal_touch():
    # 4x4 with column regions: rows/cols/regions satisfied by the identity, but diagonal touching is illegal
    regions = [[c for c in range(4)] for _ in range(4)]
    sols, _ = pz.solve(4, regions, limit=10)
    for s in sols:
        assert all(abs(s[r] - s[r + 1]) > 1 for r in range(3))
    assert sorted(sols) == [[1, 3, 0, 2], [2, 0, 3, 1]]
    assert not pz.is_valid_placement(4, regions, [(0, 0), (1, 1), (2, 2), (3, 3)])


def test_solver_detects_multiple_solutions():
    regions = [[c for c in range(4)] for _ in range(4)]
    assert pz.count_solutions(4, regions) == 2
    assert not pz.has_unique_solution(4, regions)


def test_contiguity_check():
    good = [[0, 0, 1, 1], [0, 2, 2, 1], [3, 3, 2, 1], [3, 3, 2, 2]]
    bad = [[0, 1, 0, 1], [2, 2, 2, 1], [3, 3, 2, 1], [3, 3, 2, 2]]
    assert pz.regions_are_contiguous(4, good)
    assert not pz.regions_are_contiguous(4, bad)


# ---------------------------------------------------------------- hint cap
@pytest.mark.parametrize("size,cap", [(2, 0), (3, 1), (5, 3), (8, 6), (10, 8)])
def test_hint_cap(size, cap):
    assert rules.max_hints_allowed(size) == cap
    assert rules.clamp_hints(99, size) == cap
    assert rules.clamp_hints(-5, size) == 0


def test_hints_after_level_adds_lives_and_clamps():
    assert rules.hints_after_level(1, 3, 6) == 4
    assert rules.hints_after_level(3, 3, 5) == 3        # 5x5 cap is 3
    assert rules.hints_after_level(0, 0, 7) == 0


def test_level_state_clamps_bank_and_hint_reveals_correct_cell():
    p = pz.generate(5, seed=7)
    st = LevelState(p, rules.level_spec(1), hints=10)
    assert st.hints == 3
    cell = st.use_hint(random.Random(0))
    assert cell in p.solution_cells() and st.marks[cell[0]][cell[1]] == Mark.PENGUIN
    assert st.hints == 2 and st.hints_used == 1
    # auto-X marks every blocked cell
    assert all(st.marks[r][c] != Mark.EMPTY for r, c in st.blocked_by(cell))


def test_hints_never_exceed_missing_penguins():
    p = pz.generate(5, seed=8)
    st = LevelState(p, rules.level_spec(1), hints=3)
    for r, c in list(p.solution_cells())[:3]:
        st.place((r, c))
    assert st.hints_available == 2


# --------------------------------------------------------------- game flow
def test_wrong_placement_costs_life_and_x_is_free():
    p = pz.generate(6, seed=1)
    st = LevelState(p, rules.level_spec(4), hints=0)
    wrong = [(r, c) for r in range(6) for c in range(6) if (r, c) not in p.solution_cells()]
    assert st.toggle_x(wrong[0]) == Result.MARKED and st.lives == 3
    assert st.place(wrong[0]) == Result.WRONG and st.lives == 2
    assert st.marks[wrong[0][0]][wrong[0][1]] == Mark.X
    assert st.place(wrong[1]) == Result.WRONG
    assert st.place(wrong[2]) == Result.LOST and st.finished and not st.won


def test_cycle_and_solve():
    p = pz.generate(5, seed=2)
    st = LevelState(p, rules.level_spec(1), hints=0, auto_x=False)
    cells = sorted(p.solution_cells())
    assert st.cycle(cells[0]) == Result.MARKED
    assert st.marks[cells[0][0]][cells[0][1]] == Mark.X
    assert st.cycle(cells[0]) == Result.PLACED
    assert st.cycle(cells[0]) == Result.MARKED       # penguin -> empty
    results = [st.place(c) for c in cells]
    assert results[-1] == Result.SOLVED and st.won and st.lives == 3


# ----------------------------------------------------------------- scoring
def test_score_rules():
    s = rules.score_level(5, elapsed_seconds=0, lives_left=3, hints_used=0)
    assert s.base == 400 and s.time_bonus == 400 and s.lives_bonus == 375 and s.total == 1175
    slow = rules.score_level(5, elapsed_seconds=1000, lives_left=1, hints_used=2)
    assert slow.time_bonus == 0 and slow.total == 400 + 125 - 300
    assert rules.score_level(5, 1000, 0, 50).total == 0          # never negative
    assert rules.score_level(5, 30, 3, 0).total > rules.score_level(5, 60, 3, 0).total
    assert rules.score_level(5, 30, 3, 0).total > rules.score_level(5, 30, 2, 0).total
    assert rules.score_level(5, 30, 3, 0).total > rules.score_level(5, 30, 3, 1).total
    assert rules.score_level(9, 100, 3, 0).total > rules.score_level(5, 100, 3, 0).total


def test_level_progression():
    sizes = [rules.level_spec(lv).size for lv in range(1, 22)]
    assert sizes[:3] == [5, 5, 5] and sizes[3] == 6
    assert sizes == sorted(sizes) and max(sizes) == 10


# ----------------------------------------------------------------- storage
def test_store_roundtrip(tmp_path):
    st = Store(tmp_path / "p.json")
    st.set_run(4, 1234, 2)
    st.record_level(900, 3, 5, 61)
    assert st.finish_run(1234, 4)
    st.save()
    again = Store(tmp_path / "p.json")
    assert again.run == {"level": 4, "total": 1234, "hints": 2}
    assert again.data["highscores"][0]["total"] == 1234
    assert again.data["best_levels"][0]["score"] == 900
