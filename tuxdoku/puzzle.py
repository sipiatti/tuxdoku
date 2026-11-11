"""Puzzle model, solver and generator for Tuxdoku.

Rules (Queens / one-star "Star Battle" style):
  * the N x N grid is split into N contiguous coloured regions,
  * exactly one penguin in every row, every column and every region,
  * no two penguins touch, not even diagonally.

Pure Python, no pygame dependency, so it is easy to unit-test.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

Cell = tuple[int, int]  # (row, col)

NEIGHBOURS_4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
NEIGHBOURS_8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


@dataclass
class Puzzle:
    size: int
    regions: list[list[int]]          # regions[r][c] -> region id 0..size-1
    solution: list[int]               # solution[r] -> column of the penguin in row r
    search_nodes: int = 0             # solver effort, a rough difficulty measure
    seed: int | None = field(default=None, compare=False)

    def solution_cells(self) -> set[Cell]:
        return {(r, c) for r, c in enumerate(self.solution)}

    def region_cells(self, rid: int) -> list[Cell]:
        return [(r, c) for r in range(self.size) for c in range(self.size) if self.regions[r][c] == rid]

    def to_dict(self) -> dict:
        return {"size": self.size, "regions": self.regions, "solution": self.solution,
                "search_nodes": self.search_nodes, "seed": self.seed}

    @classmethod
    def from_dict(cls, d: dict) -> "Puzzle":
        return cls(d["size"], [list(r) for r in d["regions"]], list(d["solution"]),
                   d.get("search_nodes", 0), d.get("seed"))


# --------------------------------------------------------------------------- rules
def cells_touch(a: Cell, b: Cell) -> bool:
    """True if two different cells are neighbours in any of the 8 directions."""
    return a != b and abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1


def is_valid_placement(size: int, regions: list[list[int]], penguins: set[Cell] | list[Cell]) -> bool:
    """Check a complete placement against every rule."""
    penguins = list(penguins)
    if len(penguins) != size:
        return False
    rows = {r for r, _ in penguins}
    cols = {c for _, c in penguins}
    regs = {regions[r][c] for r, c in penguins}
    if len(rows) != size or len(cols) != size or len(regs) != size:
        return False
    for i, a in enumerate(penguins):
        for b in penguins[i + 1:]:
            if cells_touch(a, b):
                return False
    return True


def regions_are_contiguous(size: int, regions: list[list[int]]) -> bool:
    """Every region id 0..size-1 exists and forms one 4-connected blob."""
    for rid in range(size):
        cells = [(r, c) for r in range(size) for c in range(size) if regions[r][c] == rid]
        if not cells:
            return False
        seen = {cells[0]}
        stack = [cells[0]]
        while stack:
            r, c = stack.pop()
            for dr, dc in NEIGHBOURS_4:
                nr, nc = r + dr, c + dc
                if 0 <= nr < size and 0 <= nc < size and (nr, nc) not in seen and regions[nr][nc] == rid:
                    seen.add((nr, nc))
                    stack.append((nr, nc))
        if len(seen) != len(cells):
            return False
    return True


# -------------------------------------------------------------------------- solver
def solve(size: int, regions: list[list[int]], limit: int = 2) -> tuple[list[list[int]], int]:
    """Find up to ``limit`` solutions. Returns (solutions, search_nodes).

    Exact-cover style backtracking on bit masks: the free cells are one Python
    int with bit ``r*size+c``. At every step the most constrained unit (row,
    column or region with the fewest free cells) is branched on, and placing a
    penguin clears its row, column, region and 8 neighbours. ``search_nodes``
    (number of tentative placements) is used as a rough difficulty measure.
    """
    n = size
    rows = [sum(1 << (r * n + c) for c in range(n)) for r in range(n)]
    cols = [sum(1 << (r * n + c) for r in range(n)) for c in range(n)]
    regs = [0] * n
    for r in range(n):
        for c in range(n):
            regs[regions[r][c]] |= 1 << (r * n + c)
    block = []  # per cell: mask of everything a penguin there rules out (incl. itself)
    for r in range(n):
        for c in range(n):
            m = rows[r] | cols[c] | regs[regions[r][c]]
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < n and 0 <= nc < n:
                        m |= 1 << (nr * n + nc)
            block.append(m)
    units = rows + cols + regs
    solutions: list[list[int]] = []
    chosen: list[int] = []
    nodes = 0

    def rec(free: int, open_units: list[int]) -> bool:
        nonlocal nodes
        if not open_units:
            sol = [0] * n
            for idx in chosen:
                sol[idx // n] = idx % n
            solutions.append(sol)
            return len(solutions) >= limit
        best_unit = -1
        best_cnt = 1 << 30
        for u in open_units:
            cnt = (units[u] & free).bit_count()
            if cnt < best_cnt:
                best_cnt, best_unit = cnt, u
                if cnt <= 1:
                    break
        if best_cnt == 0:
            return False
        cand = units[best_unit] & free
        while cand:
            low = cand & -cand
            idx = low.bit_length() - 1
            cand ^= low
            nodes += 1
            r, c = divmod(idx, n)
            done = (r, n + c, 2 * n + regions[r][c])
            chosen.append(idx)
            if rec(free & ~block[idx], [u for u in open_units if u not in done]):
                return True
            chosen.pop()
        return False

    rec((1 << (n * n)) - 1, list(range(3 * n)))
    return solutions, nodes


def count_solutions(size: int, regions: list[list[int]], limit: int = 2) -> int:
    return len(solve(size, regions, limit)[0])


def has_unique_solution(size: int, regions: list[list[int]]) -> bool:
    return count_solutions(size, regions, 2) == 1


# ----------------------------------------------------------------------- generator
def random_placement(size: int, rng: random.Random) -> list[int]:
    """Random column per row: a permutation where consecutive rows differ by > 1."""
    placed: list[int] = []

    def rec(r: int, used: set[int]) -> bool:
        if r == size:
            return True
        options = [c for c in range(size) if c not in used and (r == 0 or abs(c - placed[-1]) > 1)]
        rng.shuffle(options)
        for c in options:
            placed.append(c)
            used.add(c)
            if rec(r + 1, used):
                return True
            placed.pop()
            used.discard(c)
        return False

    if size < 4 or not rec(0, set()):
        raise ValueError(f"no valid placement exists for size {size}")
    return placed


def grow_regions(size: int, seeds: list[Cell], rng: random.Random) -> list[list[int]]:
    """Grow one contiguous region around each seed by random frontier expansion.

    Region growth is weighted towards smaller regions so sizes stay reasonably
    balanced, while still producing pleasantly irregular shapes.
    """
    regions = [[-1] * size for _ in range(size)]
    members: list[list[Cell]] = []
    for rid, (r, c) in enumerate(seeds):
        regions[r][c] = rid
        members.append([(r, c)])
    remaining = size * size - len(seeds)
    while remaining:
        # pick a region (smaller ones more likely), then a random free neighbour of it
        order = sorted(range(size), key=lambda i: len(members[i]) + rng.random() * size * 0.8)
        for rid in order:
            frontier = []
            for r, c in members[rid]:
                for dr, dc in NEIGHBOURS_4:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < size and 0 <= nc < size and regions[nr][nc] == -1:
                        frontier.append((nr, nc))
            if frontier:
                nr, nc = rng.choice(frontier)
                regions[nr][nc] = rid
                members[rid].append((nr, nc))
                remaining -= 1
                break
    return regions


def _can_give_away(size: int, regions: list[list[int]], cell: Cell, protected: set[Cell]) -> bool:
    """Can ``cell`` leave its region without disconnecting/emptying it?"""
    if cell in protected:
        return False
    r0, c0 = cell
    rid = regions[r0][c0]
    rest = [(r, c) for r in range(size) for c in range(size) if regions[r][c] == rid and (r, c) != cell]
    if not rest:
        return False
    seen = {rest[0]}
    stack = [rest[0]]
    while stack:
        r, c = stack.pop()
        for dr, dc in NEIGHBOURS_4:
            n = (r + dr, c + dc)
            if n != cell and 0 <= n[0] < size and 0 <= n[1] < size and n not in seen and regions[n[0]][n[1]] == rid:
                seen.add(n)
                stack.append(n)
    return len(seen) == len(rest)


def make_unique(size: int, regions: list[list[int]], solution: list[int], rng: random.Random,
                max_steps: int = 400) -> bool:
    """Tweak region borders (in place) until ``solution`` is the only solution.

    While another solution exists, take one of its penguins that is not part of
    the intended solution and hand that cell over to a neighbouring region.
    The intended penguins never move, so the intended solution stays valid.
    """
    protected = {(r, c) for r, c in enumerate(solution)}
    for _ in range(max_steps):
        sols, _ = solve(size, regions, 2)
        others = [s for s in sols if s != solution]
        if not others:
            return True
        alt = others[0]
        candidates = [(r, c) for r, c in enumerate(alt) if (r, c) not in protected]
        rng.shuffle(candidates)
        moved = False
        for cell in candidates:
            if not _can_give_away(size, regions, cell, protected):
                continue
            r, c = cell
            neigh = []
            for dr, dc in NEIGHBOURS_4:
                nr, nc = r + dr, c + dc
                if 0 <= nr < size and 0 <= nc < size and regions[nr][nc] != regions[r][c]:
                    neigh.append(regions[nr][nc])
            if neigh:
                regions[r][c] = rng.choice(neigh)
                moved = True
                break
        if not moved:
            return False
    return False


def generate(size: int, seed: int | None = None, candidates: int = 1) -> Puzzle:
    """Generate a puzzle with exactly one solution.

    ``candidates`` > 1 generates several unique puzzles and keeps the one the
    solver had to work hardest on (a cheap difficulty knob).
    """
    if seed is None:
        seed = random.randrange(1 << 30)
    rng = random.Random(seed)
    best: Puzzle | None = None
    made = 0
    while made < candidates:
        solution = random_placement(size, rng)
        seeds = [(r, c) for r, c in enumerate(solution)]
        regions = grow_regions(size, seeds, rng)
        if not make_unique(size, regions, solution, rng):
            continue
        sols, nodes = solve(size, regions, 2)
        assert len(sols) == 1 and sols[0] == solution
        made += 1
        cand = Puzzle(size, regions, solution, nodes, seed)
        if best is None or nodes > best.search_nodes:
            best = cand
    assert best is not None
    return best
