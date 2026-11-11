#!/usr/bin/env python3
"""Render Tuxdoku scenes headlessly and save PNG screenshots.

    python3 tools/screenshots.py [OUTPUT_DIR]
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("TUXDOKU_DATA_DIR", tempfile.mkdtemp(prefix="tuxdoku-shots-"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from tuxdoku.app import App, HelpScene, MenuScene, PlayScene, ScoresScene, SettingsScene  # noqa: E402
from tuxdoku.game import Mark  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/tuxdoku_screens")
out.mkdir(parents=True, exist_ok=True)
app = App(headless=True)


def run(seconds, events=()):
    steps = max(1, int(seconds * 60))
    for i in range(steps):
        app.step(1 / 60, events if i == 0 else ())


def shot(name):
    path = out / f"{name}.png"
    pygame.image.save(app.screen, str(path))
    print(path)


def play(level, seed, total=0, hints=1):
    scene = PlayScene(app, level, total, hints, seed=seed)
    app.goto(scene)
    scene.future.result()
    run(0.1)
    return scene


def motion(scene, cell):
    r = scene.cell_rect(cell)
    return pygame.event.Event(pygame.MOUSEMOTION, pos=r.center, rel=(0, 0), buttons=(0, 0, 0))


# demo high scores
app.store.record_level(1480, 3, 5, 52)
app.store.record_level(2210, 6, 6, 98)
app.store.finish_run(5120, 7)
app.store.set_run(4, 3690, 2)
app.store.update_best_total(5120)
app.goto(MenuScene(app))
run(1.2)
shot("01_menu")

# small board in progress
s = play(2, seed=11, total=1175, hints=2)
sol = sorted(s.state.puzzle.solution_cells())
s.act(sol[0], "place")
s.act(sol[3], "place")
wrong = next((r, c) for r in range(5) for c in range(5)
             if s.state.marks[r][c] == Mark.AUTO_X and (r, c) not in s.state.puzzle.solution_cells())
s.state.set_x((4, 4), True) if s.state.marks[4][4] == Mark.EMPTY else None
s.state.elapsed = 37
run(0.6, [motion(s, sol[2])])
s.act(wrong, "place")
run(0.12)
shot("02_board_5x5")

# large board in progress
s = play(16, seed=5, total=24310, hints=5)
sol = sorted(s.state.puzzle.solution_cells())
for cell in sol[:4]:
    s.act(cell, "place")
s.state.auto_x = False
for c in range(10):
    if s.state.marks[9][c] == Mark.EMPTY and c % 3 == 0:
        s.state.set_x((9, c), True)
s.state.elapsed = 141
app.audio.toggle_music()           # show the muted-music icon state
run(0.6, [motion(s, sol[6])])
shot("03_board_10x10")
app.audio.toggle_music()

# level complete
s = play(5, seed=21, total=3690, hints=2)
sol = sorted(s.state.puzzle.solution_cells())
s.state.elapsed = 64
wrong = next((r, c) for r in range(s.n) for c in range(s.n) if (r, c) not in s.state.puzzle.solution_cells())
s.act(wrong, "place")
s.hint()
for cell in sol:
    if s.state.marks[cell[0]][cell[1]] != Mark.PENGUIN:
        s.act(cell, "place")
run(1.25)
shot("04_level_complete")

# game over
s = play(8, seed=3, total=8000, hints=3)
bad = [(r, c) for r in range(s.n) for c in range(s.n) if (r, c) not in s.state.puzzle.solution_cells()]
for cell in bad[:3]:
    s.act(cell, "place")
run(1.4)
shot("05_game_over")

app.goto(HelpScene(app))
run(0.5)
shot("06_help")
app.goto(ScoresScene(app))
run(0.5)
shot("07_scores")
app.audio.set_music_volume(0.65)
app.audio.toggle_sfx()
app.goto(SettingsScene(app, MenuScene(app)))
run(0.5)
shot("08_settings")
app.audio.toggle_sfx()
