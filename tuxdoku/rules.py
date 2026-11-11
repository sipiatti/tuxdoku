"""Game rules that are easy to tweak: levels, hint cap and scoring.

Kept free of pygame so they can be unit-tested.
"""
from __future__ import annotations

from dataclasses import dataclass

LIVES_PER_LEVEL = 3
STARTING_HINTS = 1          # hints in the bank when a brand new game starts
MIN_SIZE = 5
MAX_SIZE = 10
LEVELS_PER_SIZE = 3


# ----------------------------------------------------------------------- levels
@dataclass(frozen=True)
class LevelSpec:
    level: int
    size: int          # N: board is N x N, N regions, N hidden penguins
    tier: int          # 0..LEVELS_PER_SIZE-1 position within a size (difficulty step)
    candidates: int    # generator keeps the hardest of this many unique puzzles


def level_spec(level: int) -> LevelSpec:
    """Level 1-3: 5x5, 4-6: 6x6, ... 16+: 10x10 (endless)."""
    level = max(1, level)
    idx = level - 1
    size = min(MIN_SIZE + idx // LEVELS_PER_SIZE, MAX_SIZE)
    tier = idx % LEVELS_PER_SIZE if size < MAX_SIZE else min(idx - (MAX_SIZE - MIN_SIZE) * LEVELS_PER_SIZE,
                                                              LEVELS_PER_SIZE - 1)
    # later levels inside a size pick the trickiest of several candidates;
    # large boards get fewer candidates so generation stays quick.
    cap = 3 if size <= 8 else 2
    return LevelSpec(level, size, tier, min(1 + tier * (2 if size <= 8 else 1), cap + 2))


# ------------------------------------------------------------------------- hints
def hidden_penguins(size: int) -> int:
    """Number of penguins hidden on an N x N board (= N)."""
    return size


def max_hints_allowed(size: int) -> int:
    """THE hint cap: available hints may never exceed hidden penguins - 2 (never below 0).

    Change this one function to change the cap everywhere.
    """
    return max(0, hidden_penguins(size) - 2)


def clamp_hints(hints: int, size: int) -> int:
    return max(0, min(hints, max_hints_allowed(size)))


def hints_after_level(hints_left: int, lives_left: int, next_size: int) -> int:
    """Each remaining life adds one hint; the bank is then clamped to the next board's cap."""
    return clamp_hints(hints_left + max(0, lives_left), next_size)


# ------------------------------------------------------------------------ scoring
@dataclass(frozen=True)
class ScoreBreakdown:
    base: int
    time_bonus: int
    lives_bonus: int
    hint_penalty: int
    par_seconds: int

    @property
    def total(self) -> int:
        return max(0, self.base + self.time_bonus + self.lives_bonus - self.hint_penalty)


def par_seconds(size: int) -> int:
    """Target time for a board: 4 s per cell (5x5 -> 100 s, 10x10 -> 400 s)."""
    return 4 * size * size


def score_level(size: int, elapsed_seconds: float, lives_left: int, hints_used: int, tier: int = 0) -> ScoreBreakdown:
    """Score for a *completed* level (a lost level scores 0).

    base         = 40 * N * (N - 3) * (1 + 0.1 * tier)
    time_bonus   = base * max(0, par - t) / par      (finish instantly -> +100 %)
    lives_bonus  = 25 * N * lives_left
    hint_penalty = 30 * N * hints_used
    total        = max(0, base + time_bonus + lives_bonus - hint_penalty)
    """
    base = round(40 * size * (size - 3) * (1 + 0.1 * tier))
    par = par_seconds(size)
    t = max(0.0, elapsed_seconds)
    time_bonus = round(base * max(0.0, par - t) / par)
    lives_bonus = 25 * size * max(0, lives_left)
    hint_penalty = 30 * size * max(0, hints_used)
    return ScoreBreakdown(base, time_bonus, lives_bonus, hint_penalty, par)
