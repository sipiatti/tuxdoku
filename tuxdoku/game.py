"""Play state of one level (no pygame): marks, penguins, lives, hints, timer."""
from __future__ import annotations

import random
from enum import IntEnum

from .puzzle import Cell, Puzzle, cells_touch
from .rules import LIVES_PER_LEVEL, LevelSpec, clamp_hints, max_hints_allowed, score_level


class Mark(IntEnum):
    EMPTY = 0
    X = 1          # player's note: no penguin here
    AUTO_X = 2     # X added automatically (auto-X option / hint)
    PENGUIN = 3


class Result(IntEnum):
    NOTHING = 0
    MARKED = 1
    PLACED = 2
    WRONG = 3
    SOLVED = 4
    LOST = 5


class LevelState:
    def __init__(self, puzzle: Puzzle, spec: LevelSpec, hints: int, auto_x: bool = True):
        self.puzzle = puzzle
        self.spec = spec
        self.n = puzzle.size
        self.marks = [[Mark.EMPTY] * self.n for _ in range(self.n)]
        self.lives = LIVES_PER_LEVEL
        self.hints = clamp_hints(hints, self.n)   # bank clamped to this board's cap
        self.hints_at_start = self.hints
        self.hints_used = 0
        self.mistakes = 0
        self.elapsed = 0.0
        self.auto_x = auto_x
        self._solution = puzzle.solution_cells()
        self.finished = False
        self.won = False

    # ------------------------------------------------------------------ queries
    @property
    def penguins(self) -> list[Cell]:
        return [(r, c) for r in range(self.n) for c in range(self.n) if self.marks[r][c] == Mark.PENGUIN]

    def is_solution_cell(self, cell: Cell) -> bool:
        return cell in self._solution

    @property
    def hints_available(self) -> int:
        """Usable hints right now (bank, capped by max_hints_allowed, and by unfound penguins)."""
        if self.finished:
            return 0
        missing = self.n - len(self.penguins)
        return max(0, min(self.hints, max_hints_allowed(self.n), missing))

    def tick(self, dt: float) -> None:
        if not self.finished:
            self.elapsed += dt

    # ------------------------------------------------------------------ actions
    def cycle(self, cell: Cell) -> Result:
        """Left click: empty -> X -> penguin -> empty."""
        m = self.marks[cell[0]][cell[1]]
        if m == Mark.EMPTY:
            return self.set_x(cell, True)
        if m in (Mark.X, Mark.AUTO_X):
            return self.place(cell)
        return self.remove(cell)

    def set_x(self, cell: Cell, on: bool) -> Result:
        if self.finished:
            return Result.NOTHING
        r, c = cell
        m = self.marks[r][c]
        if on and m == Mark.EMPTY:
            self.marks[r][c] = Mark.X
            return Result.MARKED
        if not on and m in (Mark.X, Mark.AUTO_X):
            self.marks[r][c] = Mark.EMPTY
            return Result.MARKED
        return Result.NOTHING

    def toggle_x(self, cell: Cell) -> Result:
        m = self.marks[cell[0]][cell[1]]
        if m == Mark.PENGUIN:
            return Result.NOTHING
        return self.set_x(cell, m == Mark.EMPTY)

    def remove(self, cell: Cell) -> Result:
        r, c = cell
        if self.finished or self.marks[r][c] != Mark.PENGUIN:
            return Result.NOTHING
        self.marks[r][c] = Mark.EMPTY
        return Result.MARKED

    def place(self, cell: Cell) -> Result:
        """Try to hide a penguin. A wrong cell costs a life and becomes an X."""
        if self.finished:
            return Result.NOTHING
        r, c = cell
        if self.marks[r][c] == Mark.PENGUIN:
            return Result.NOTHING
        if cell not in self._solution:
            self.lives -= 1
            self.mistakes += 1
            self.marks[r][c] = Mark.X
            if self.lives <= 0:
                self.lives = 0
                self.finished = True
                self.won = False
                return Result.LOST
            return Result.WRONG
        self.marks[r][c] = Mark.PENGUIN
        if self.auto_x:
            self._auto_cross(cell)
        return self._check_solved() or Result.PLACED

    def use_hint(self, rng: random.Random | None = None) -> Cell | None:
        """Reveal one correct penguin (plus auto-X around it). Returns the cell or None."""
        if self.hints_available <= 0:
            return None
        rng = rng or random.Random()
        missing = [cell for cell in sorted(self._solution) if self.marks[cell[0]][cell[1]] != Mark.PENGUIN]
        if not missing:
            return None
        cell = rng.choice(missing)
        self.hints -= 1
        self.hints_used += 1
        self.marks[cell[0]][cell[1]] = Mark.PENGUIN
        self._auto_cross(cell)
        self._check_solved()
        return cell

    # ----------------------------------------------------------------- helpers
    def blocked_by(self, cell: Cell) -> list[Cell]:
        """Cells ruled out by a penguin on ``cell``: row, column, region and touching cells."""
        r0, c0 = cell
        rid = self.puzzle.regions[r0][c0]
        out = []
        for r in range(self.n):
            for c in range(self.n):
                if (r, c) == cell:
                    continue
                if r == r0 or c == c0 or self.puzzle.regions[r][c] == rid or cells_touch(cell, (r, c)):
                    out.append((r, c))
        return out

    def _auto_cross(self, cell: Cell) -> None:
        for r, c in self.blocked_by(cell):
            if self.marks[r][c] == Mark.EMPTY:
                self.marks[r][c] = Mark.AUTO_X

    def _check_solved(self) -> Result | None:
        if set(self.penguins) == self._solution:
            self.finished = True
            self.won = True
            return Result.SOLVED
        return None

    def score(self):
        return score_level(self.n, self.elapsed, self.lives, self.hints_used, self.spec.tier)
