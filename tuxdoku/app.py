"""Tuxdoku pygame application: scenes for menu, play, results, scores and help."""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from concurrent.futures import Future, ThreadPoolExecutor

import pygame

from . import __version__, rules, theme
from .game import LevelState, Mark, Result
from .puzzle import Puzzle, generate
from .resources import font, icon_path, image
from .audio import Audio
from .storage import Store
from .ui import (Button, IconButton, Particles, Slider, Snow, card, draw_background, ease_out_back, fmt_time, mix,
                 rainbow_title, text)

W, H = theme.WIDTH, theme.HEIGHT


# ============================================================ puzzle factory
class PuzzleFactory:
    """Generates puzzles on a worker thread and pre-fetches the next level."""

    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tuxdoku-gen")
        self.cache: dict[int, Future] = {}

    def request(self, level: int, seed: int | None = None) -> Future:
        fut = self.cache.pop(level, None)
        if fut is None or seed is not None:
            spec = rules.level_spec(level)
            fut = self.pool.submit(generate, spec.size, seed, spec.candidates)
        return fut

    def prefetch(self, level: int) -> None:
        if level not in self.cache:
            spec = rules.level_spec(level)
            self.cache[level] = self.pool.submit(generate, spec.size, None, spec.candidates)

    def shutdown(self):
        self.pool.shutdown(wait=False, cancel_futures=True)


# ===================================================================== scenes
class Scene:
    music: str | None = "menu"      # background track for this scene (None = keep current)

    def __init__(self, app: "App"):
        self.app = app
        self.buttons: list[Button] = []
        self.t = 0.0

    def handle(self, event):
        for b in self.buttons:
            if b.handle(event):
                return True
        return False

    def update(self, dt):
        self.t += dt
        for b in self.buttons:
            b.update(dt)

    def draw(self, surf):
        for b in self.buttons:
            b.draw(surf)

    def audio_buttons(self, positions, settings_back=None, help_back=None):
        """Round music / effects / settings (/ help) buttons; returns them for refreshing."""
        app = self.app
        out = [IconButton(positions[0], "icons/music.png", theme.BTN_MINT, app.toggle_music, tooltip="Zene (M)"),
               IconButton(positions[1], "icons/speaker.png", theme.BTN_BLUE, app.toggle_sfx, tooltip="Hangok (S)"),
               IconButton(positions[2], "icons/gear.png", theme.BTN_PURPLE,
                          lambda: app.goto(SettingsScene(app, settings_back or self)), tooltip="Beállítások")]
        if len(positions) > 3:
            out.append(IconButton(positions[3], "icons/question.png", theme.BTN_ORANGE,
                                  lambda: app.goto(HelpScene(app, help_back or self)), tooltip="Súgó"))
        self.sound_btns = out
        self.buttons += out
        return out

    def refresh_audio_buttons(self):
        btns = getattr(self, "sound_btns", None)
        if not btns:
            return
        a = self.app.audio
        btns[0].icon = "icons/music_off.png" if a.music_muted else "icons/music.png"
        btns[0].colors = theme.BTN_GREY if a.music_muted else theme.BTN_MINT
        btns[1].icon = "icons/speaker_off.png" if a.sfx_muted else "icons/speaker.png"
        btns[1].colors = theme.BTN_GREY if a.sfx_muted else theme.BTN_BLUE


class MenuScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        run = app.store.run
        x, w, h, y = W // 2 - 170, 340, 60, 286
        if run:
            self.buttons.append(Button((x, y, w, h), f"Folytatás · {run['level']}. szint", theme.BTN_MINT,
                                       action=app.continue_game))
            y += 74
        self.buttons += [
            Button((x, y, w, h), "Új játék", theme.BTN_PINK, action=app.new_game),
            Button((x, y + 74, w, h), "Hogyan játssz?", theme.BTN_BLUE, action=lambda: app.goto(HelpScene(app, self))),
            Button((x, y + 148, w, h), "Dicsőségtábla", theme.BTN_YELLOW, icon="icons/star.png",
                   action=lambda: app.goto(ScoresScene(app))),
            Button((x, y + 222, w, h), "Kilépés", theme.BTN_PURPLE, action=app.quit),
        ]
        self.audio_buttons([(W - 166, 46), (W - 106, 46), (W - 46, 46)])

    def update(self, dt):
        super().update(dt)
        self.refresh_audio_buttons()

    def draw(self, surf):
        rainbow_title(surf, "Tuxdoku", 120, (W // 2, 140), self.t)
        text(surf, "Rejtsd el a pingvineket!", 32, theme.TEXT_SOFT, "bold", center=(W // 2, 232))
        # bouncing penguins either side
        for i, (px, flip) in enumerate(((150, False), (W - 150, True))):
            bounce = abs(math.sin(self.t * 2.4 + i * 1.3)) * 22
            img = image("penguins/penguin_happy.png" if int(self.t * 0.8 + i) % 3 == 0 else "penguins/penguin.png", 190)
            if flip:
                img = pygame.transform.flip(img, True, False)
            surf.blit(img, img.get_rect(midbottom=(px, 470 - bounce)))
            sh = pygame.Surface((140, 24), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (120, 100, 170, 50 - int(bounce)), sh.get_rect())
            surf.blit(sh, sh.get_rect(center=(px, 478)))
        super().draw(surf)
        best = self.app.store.data.get("best_total", 0)
        if best:
            text(surf, f"Legjobb összpontszám: {best}", 24, theme.TEXT_SOFT, "medium", center=(W // 2, H - 26))
        text(surf, f"v{__version__}", 18, theme.TEXT_SOFT, "medium", midright=(W - 16, H - 20))

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            (self.app.continue_game if self.app.store.run else self.app.new_game)()
            return True
        return super().handle(event)


class PlayScene(Scene):
    music = "game"
    BOARD_AREA = pygame.Rect(28, 28, 664, 664)

    def __init__(self, app, level: int, total: int, hints: int, seed: int | None = None):
        super().__init__(app)
        self.level = level
        self.total = total
        self.hints_bank = hints
        self.spec = rules.level_spec(level)
        self.future = app.factory.request(level, seed)
        self.state: LevelState | None = None
        self.particles = Particles()
        self.anims: dict[tuple, float] = {}       # cell -> pop start time
        self.wrong: dict[tuple, float] = {}       # cell -> time of mistake
        self.heart_break: list[float] = []
        self.shake = 0.0
        self.cursor = (0, 0)
        self.hover: tuple | None = None
        self.drag_mode: str | None = None         # "add" / "remove" X while dragging
        self.drag_button = 0
        self.overlay: Scene | None = None
        self.paused_time = 0.0
        px = 724
        self.hint_btn = Button((px, 432, 272, 62), "Tipp", theme.BTN_YELLOW, icon="icons/bulb.png", action=self.hint)
        self.autox_btn = Button((px, 508, 272, 54), "", theme.BTN_BLUE, size=24, action=self.toggle_auto_x)
        self.clear_btn = Button((px, 574, 132, 54), "X-ek", theme.BTN_PURPLE, icon="icons/eraser.png", size=24,
                                action=self.clear_x)
        self.menu_btn = Button((px + 140, 574, 132, 54), "Menü", theme.BTN_PINK, size=26, action=self.to_menu)
        self.buttons = [self.hint_btn, self.autox_btn, self.clear_btn, self.menu_btn]
        self.audio_buttons([(px + 28 + i * 72, 672) for i in range(4)])
        self._last_drag_sound = 0.0

    # ------------------------------------------------------------ geometry
    @property
    def n(self):
        return self.spec.size

    def board_rect(self) -> pygame.Rect:
        cell = self.BOARD_AREA.w // self.n
        size = cell * self.n
        r = pygame.Rect(0, 0, size, size)
        r.center = self.BOARD_AREA.center
        return r

    def cell_size(self):
        return self.BOARD_AREA.w // self.n

    def cell_at(self, pos):
        br = self.board_rect()
        if not br.collidepoint(pos):
            return None
        cs = self.cell_size()
        return ((pos[1] - br.y) // cs, (pos[0] - br.x) // cs)

    def cell_rect(self, cell):
        br = self.board_rect()
        cs = self.cell_size()
        return pygame.Rect(br.x + cell[1] * cs, br.y + cell[0] * cs, cs, cs)

    # ------------------------------------------------------------- actions
    def _start_state(self, puzzle: Puzzle):
        self.state = LevelState(puzzle, self.spec, self.hints_bank, self.app.store.data["settings"]["auto_x"])
        self.app.factory.prefetch(self.level + 1)

    def hint(self):
        if not self.state or self.state.finished:
            return
        cell = self.state.use_hint()
        if cell:
            self.anims[cell] = self.t
            r = self.cell_rect(cell)
            self.particles.sparkle(*r.center, count=18)
            self.app.audio.play("hint")
            self._after_move(Result.SOLVED if self.state.won else Result.PLACED)

    def toggle_auto_x(self):
        s = self.app.store.data["settings"]
        s["auto_x"] = not s["auto_x"]
        if self.state:
            self.state.auto_x = s["auto_x"]
        self.app.store.save()

    def clear_x(self):
        if not self.state or self.state.finished:
            return
        self.app.audio.play("unmark")
        for r in range(self.n):
            for c in range(self.n):
                if self.state.marks[r][c] in (Mark.X, Mark.AUTO_X):
                    self.state.marks[r][c] = Mark.EMPTY

    def to_menu(self):
        self.app.goto(MenuScene(self.app))

    def act(self, cell, how: str):
        st = self.state
        if not st or st.finished:
            return
        if how == "cycle":
            res = st.cycle(cell)
        elif how == "toggle_x":
            res = st.toggle_x(cell)
        elif how == "place":
            res = st.place(cell)
        else:
            res = Result.NOTHING
        audio = self.app.audio
        if res in (Result.PLACED, Result.SOLVED):
            self.anims[cell] = self.t
            audio.play("place")
        elif res == Result.MARKED:
            m = st.marks[cell[0]][cell[1]]
            audio.play("mark" if m in (Mark.X, Mark.AUTO_X) else "unmark")
        elif res in (Result.WRONG, Result.LOST):
            audio.play("wrong")
            self.wrong[cell] = self.t
            self.heart_break.append(self.t)
            self.shake = 0.35
        self._after_move(res)

    def _after_move(self, res):
        st = self.state
        if res == Result.SOLVED or (st and st.won):
            self.app.level_won(self)
        elif res == Result.LOST:
            self.app.level_lost(self)

    # -------------------------------------------------------------- events
    def handle(self, event):
        if self.overlay:
            return self.overlay.handle(event)
        if super().handle(event):
            return True
        st = self.state
        if not st:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.cell_at(event.pos)
            if self.drag_mode and self.hover and self.hover != self._last_drag:
                self._last_drag = self.hover
                if st.set_x(self.hover, self.drag_mode == "add") == Result.MARKED and self.t - self._last_drag_sound > 0.05:
                    self._last_drag_sound = self.t
                    self.app.audio.play("mark" if self.drag_mode == "add" else "unmark", 0.6)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            cell = self.cell_at(event.pos)
            if cell is None:
                return False
            self.cursor = cell
            m = st.marks[cell[0]][cell[1]]
            self._last_drag = cell
            if event.button == 1:
                if m == Mark.EMPTY:
                    self.drag_mode = "add"
                self.act(cell, "cycle")
            else:
                if m == Mark.EMPTY:
                    self.drag_mode = "add"
                elif m in (Mark.X, Mark.AUTO_X):
                    self.drag_mode = "remove"
                self.act(cell, "toggle_x")
            return True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.drag_mode = None
        elif event.type == pygame.KEYDOWN:
            r, c = self.cursor
            moves = {pygame.K_LEFT: (0, -1), pygame.K_RIGHT: (0, 1), pygame.K_UP: (-1, 0), pygame.K_DOWN: (1, 0)}
            if event.key in moves:
                dr, dc = moves[event.key]
                self.cursor = ((r + dr) % self.n, (c + dc) % self.n)
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.act(self.cursor, "cycle")
            elif event.key == pygame.K_x:
                self.act(self.cursor, "toggle_x")
            elif event.key == pygame.K_p:
                self.act(self.cursor, "place")
            elif event.key in (pygame.K_BACKSPACE, pygame.K_DELETE):
                st.remove(self.cursor)
                st.set_x(self.cursor, False)
            elif event.key == pygame.K_h:
                self.hint()
            elif event.key == pygame.K_ESCAPE:
                self.to_menu()
            else:
                return False
            return True
        return False

    def update(self, dt):
        super().update(dt)
        self.particles.update(dt)
        self.shake = max(0.0, self.shake - dt)
        if self.state is None and self.future.done():
            self._start_state(self.future.result())
        if self.state and not self.overlay:
            self.state.tick(dt)
        st = self.state
        self.hint_btn.enabled = bool(st and st.hints_available > 0)
        self.hint_btn.label = f"Tipp: {st.hints_available if st else 0}  (max {rules.max_hints_allowed(self.n)})"
        self.autox_btn.label = "Automatikus X: " + ("BE" if self.app.store.data["settings"]["auto_x"] else "KI")
        self.autox_btn.colors = theme.BTN_BLUE if self.app.store.data["settings"]["auto_x"] else theme.BTN_GREY
        self.refresh_audio_buttons()
        if self.overlay:
            self.overlay.update(dt)

    # ---------------------------------------------------------------- draw
    def draw(self, surf):
        ox = int(math.sin(self.t * 70) * 7 * (self.shake / 0.35)) if self.shake else 0
        board = pygame.Surface((W, H), pygame.SRCALPHA)
        self.draw_board(board)
        surf.blit(board, (ox, 0))
        self.draw_panel(surf)
        self.particles.draw(surf)
        if self.overlay:
            self.overlay.draw(surf)

    def draw_board(self, surf):
        br = self.board_rect()
        card(surf, br.inflate(28, 28), radius=28, shadow=8)
        st = self.state
        if st is None:
            ang = self.t * 4
            img = image("penguins/penguin.png", 150)
            rot = pygame.transform.rotozoom(img, math.sin(ang) * 12, 1.0)
            surf.blit(rot, rot.get_rect(center=(br.centerx, br.centery - 30)))
            dots = "." * (int(self.t * 3) % 4)
            text(surf, f"A pingvinek elbújnak{dots}", 34, theme.TEXT, center=(br.centerx, br.centery + 80))
            return
        n, cs, regions = self.n, self.cell_size(), st.puzzle.regions
        palette = self.app.region_palette(st.puzzle)
        focus = self.hover or self.cursor
        for r in range(n):
            for c in range(n):
                rect = self.cell_rect((r, c))
                col = palette[regions[r][c]]
                if focus and (r == focus[0] or c == focus[1]):
                    col = mix(col, theme.WHITE, 0.28)
                if (r, c) == self.hover:
                    col = mix(col, theme.WHITE, 0.45)
                pygame.draw.rect(surf, col, rect)
        # thin grid lines
        for i in range(1, n):
            x = br.x + i * cs
            y = br.y + i * cs
            pygame.draw.line(surf, mix(theme.GRID_LINE, theme.REGION_BORDER, 0.12), (x, br.y), (x, br.bottom), 1)
            pygame.draw.line(surf, mix(theme.GRID_LINE, theme.REGION_BORDER, 0.12), (br.x, y), (br.right, y), 1)
        # thick region borders
        bw = 4 if n <= 8 else 3
        for r in range(n):
            for c in range(n):
                rect = self.cell_rect((r, c))
                if c + 1 < n and regions[r][c] != regions[r][c + 1]:
                    pygame.draw.line(surf, theme.REGION_BORDER, (rect.right, rect.top - 1), (rect.right, rect.bottom + 1), bw)
                if r + 1 < n and regions[r][c] != regions[r + 1][c]:
                    pygame.draw.line(surf, theme.REGION_BORDER, (rect.left - 1, rect.bottom), (rect.right + 1, rect.bottom), bw)
        pygame.draw.rect(surf, theme.REGION_BORDER, br.inflate(6, 6), 6, border_radius=8)
        # keyboard cursor
        if self.hover is None:
            pygame.draw.rect(surf, (255, 255, 255), self.cell_rect(self.cursor).inflate(-6, -6), 4, border_radius=8)
        # marks
        for r in range(n):
            for c in range(n):
                m = st.marks[r][c]
                rect = self.cell_rect((r, c))
                if m == Mark.X:
                    self.draw_x(surf, rect, theme.X_COLOR, 0.30, 5 if n <= 8 else 4)
                elif m == Mark.AUTO_X:
                    pygame.draw.circle(surf, theme.AUTO_X_COLOR, rect.center, max(3, cs // 14))
                elif m == Mark.PENGUIN:
                    start = self.anims.get((r, c))
                    k = ease_out_back((self.t - start) / 0.35) if start is not None else 1.0
                    happy = st.won
                    img = image("penguins/penguin_happy.png" if happy else "penguins/penguin.png", int(cs * 0.9))
                    if k != 1.0:
                        img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * k)),) * 2)
                    bob = math.sin(self.t * 3 + r + c) * 2 if happy else 0
                    surf.blit(img, img.get_rect(center=(rect.centerx, rect.centery + bob)))
        # mistakes: red pulse + sad penguin fading out
        for cell, t0 in list(self.wrong.items()):
            age = self.t - t0
            if age > 0.9:
                del self.wrong[cell]
                continue
            rect = self.cell_rect(cell)
            a = int(200 * (1 - age / 0.9))
            ov = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(ov, (*theme.WRONG, a), ov.get_rect(), border_radius=6)
            surf.blit(ov, rect)
            img = image("penguins/penguin_sad.png", int(cs * 0.85)).copy()
            img.set_alpha(int(255 * (1 - age / 0.9)))
            surf.blit(img, img.get_rect(center=(rect.centerx, rect.centery - age * 20)))

    @staticmethod
    def draw_x(surf, rect, color, frac, width):
        cx, cy = rect.center
        d = rect.w * frac / 1.0 * 0.6
        pygame.draw.line(surf, color, (cx - d, cy - d), (cx + d, cy + d), width)
        pygame.draw.line(surf, color, (cx - d, cy + d), (cx + d, cy - d), width)
        for p in ((cx - d, cy - d), (cx + d, cy + d), (cx - d, cy + d), (cx + d, cy - d)):
            pygame.draw.circle(surf, color, p, width // 2)

    def draw_panel(self, surf):
        st = self.state
        px = 712
        card(surf, (px, 28, 296, 112), radius=24)
        text(surf, f"{self.level}. szint", 40, theme.TEXT, "black", midleft=(px + 22, 66))
        text(surf, f"{self.n}×{self.n}", 30, (255, 112, 150), "black", midright=(px + 276, 66))
        text(surf, f"Összesen: {self.total} pont", 24, theme.TEXT_SOFT, "medium", midleft=(px + 22, 112))
        # timer + lives
        card(surf, (px, 154, 296, 124), radius=24)
        elapsed = st.elapsed if st else 0
        text(surf, "Idő", 22, theme.TEXT_SOFT, "medium", midleft=(px + 22, 180))
        text(surf, fmt_time(elapsed), 40, (70, 160, 255), "black", midleft=(px + 22, 216))
        par = rules.par_seconds(self.n)
        bar = pygame.Rect(px + 22, 250, 252, 12)
        pygame.draw.rect(surf, (234, 226, 248), bar, border_radius=6)
        frac = max(0.0, 1 - elapsed / par)
        if frac > 0:
            bar_col = mix((255, 209, 102), (110, 214, 160), (frac - 0.5) * 2) if frac > 0.5 else \
                mix((255, 120, 150), (255, 209, 102), frac * 2)
            pygame.draw.rect(surf, bar_col,
                             (bar.x, bar.y, max(12, int(bar.w * frac)), bar.h), border_radius=6)
        lives = st.lives if st else rules.LIVES_PER_LEVEL
        for i in range(rules.LIVES_PER_LEVEL):
            alive = i < lives
            sz = 44
            broke = [t for t in self.heart_break if self.t - t < 0.6]
            if not alive and i == lives and broke:
                sz = int(44 + 18 * (1 - (self.t - broke[-1]) / 0.6))
            img = image("icons/heart.png" if alive else "icons/heart_empty.png", sz)
            surf.blit(img, img.get_rect(center=(px + 176 + i * 42, 204)))
        # penguin progress
        card(surf, (px, 292, 296, 124), radius=24)
        found = len(st.penguins) if st else 0
        text(surf, f"Pingvinek: {found} / {self.n}", 26, theme.TEXT, midleft=(px + 22, 320))
        per_row = 5
        ic = 40
        for i in range(self.n):
            img = image("penguins/penguin.png", ic) if i < found else None
            x = px + 22 + (i % per_row) * 52
            y = 344 + (i // per_row) * 34
            if img:
                surf.blit(img, (x, y - 4))
            else:
                pygame.draw.circle(surf, (234, 226, 248), (x + ic // 2, y + ic // 2 - 4), 13)
        super().draw(surf)


class ResultOverlay(Scene):
    """Level complete / game over card drawn on top of the play scene."""

    def __init__(self, app, play: PlayScene, won: bool, breakdown=None, new_hints=0, gained=0):
        super().__init__(app)
        self.play = play
        self.won = won
        self.breakdown = breakdown
        self.new_hints = new_hints
        self.gained = gained
        self.particles = Particles()
        self.delay = 0.6 if won else 0.9
        cx = W // 2
        if won:
            self.buttons = [Button((cx - 250, 572, 240, 64), "Menü", theme.BTN_PURPLE, action=play.to_menu),
                            Button((cx + 10, 572, 240, 64), "Következő szint", theme.BTN_MINT, size=28,
                                   action=app.next_level)]
        else:
            self.buttons = [Button((cx - 250, 520, 240, 64), "Menü", theme.BTN_PURPLE, action=play.to_menu),
                            Button((cx + 10, 520, 240, 64), "Újrapróbálom", theme.BTN_PINK, action=app.retry_level)]
        self._fired = False
        self._sounded = False

    def handle(self, event):
        if self.t < self.delay:
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.buttons[1].action()
            return True
        return super().handle(event)

    def update(self, dt):
        super().update(dt)
        self.particles.update(dt)
        if not self._sounded and self.t >= self.delay:
            self._sounded = True
            self.app.audio.play("fanfare" if self.won else "gameover")
            self.app.audio.duck(2.6 if self.won else 2.2)
        if self.won and self._fired and random.random() < dt * 30:
            self.particles.rain(random.uniform(0, W))
        if self.won and not self._fired and self.t >= self.delay:
            self._fired = True
            for x in (W * 0.12, W * 0.5, W * 0.88):
                self.particles.confetti(x, H * 0.55, 60, spread=560)

    def draw(self, surf):
        if self.t < self.delay:
            return
        k = min(1.0, (self.t - self.delay) / 0.3)
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((90, 70, 140, int(110 * k)))
        surf.blit(dim, (0, 0))
        s = ease_out_back(k)
        cw, ch = (620, 610) if self.won else (560, 440)
        rect = pygame.Rect(0, 0, int(cw * s), int(ch * s))
        rect.center = (W // 2, H // 2)
        self.particles.draw(surf)
        card(surf, rect, radius=36, shadow=10, border=(255, 200, 225))
        if k < 1:
            return
        top = rect.top
        if self.won:
            bd = self.breakdown
            peng = image("penguins/penguin_happy.png", 130)
            bob = abs(math.sin(self.t * 4)) * 10
            surf.blit(peng, peng.get_rect(midbottom=(W // 2, top + 128 - bob)))
            stars = self.play.state.lives
            text(surf, "Szint teljesítve!", 50, (255, 112, 150), "black", center=(W // 2, top + 160), outline=theme.WHITE)
            for i in range(3):
                img = image("icons/star.png", 54)
                if i >= stars:
                    img = img.copy()
                    img.set_alpha(55)
                wob = math.sin(self.t * 3 + i) * 4 if i < stars else 0
                surf.blit(img, img.get_rect(center=(W // 2 + (i - 1) * 66, top + 214 + wob)))
            st = self.play.state
            rows = [("Alappont", f"{bd.base}"),
                    (f"Időbónusz ({fmt_time(st.elapsed)} / cél {fmt_time(bd.par_seconds)})", f"+{bd.time_bonus}"),
                    (f"Életbónusz ({st.lives} élet)", f"+{bd.lives_bonus}"),
                    (f"Felhasznált tipp ({st.hints_used})", f"−{bd.hint_penalty}")]
            y = top + 266
            for label, val in rows:
                text(surf, label, 26, theme.TEXT, "medium", midleft=(rect.x + 90, y))
                text(surf, val, 26, theme.TEXT, "bold", midright=(rect.right - 90, y))
                y += 36
            pygame.draw.line(surf, theme.CARD_BORDER, (rect.x + 80, y - 10), (rect.right - 80, y - 10), 3)
            text(surf, "Pontszám", 32, theme.TEXT, "black", midleft=(rect.x + 90, y + 18))
            text(surf, f"{bd.total}", 38, (70, 160, 255), "black", midright=(rect.right - 90, y + 18))
            text(surf, f"+{self.gained} tipp a megmaradt életekért  ·  Tippek: {self.new_hints}", 22,
                 theme.TEXT_SOFT, "medium", center=(W // 2, y + 62))
        else:
            peng = image("penguins/penguin_sad.png", 140)
            surf.blit(peng, peng.get_rect(midbottom=(W // 2, top + 160)))
            text(surf, "Elfogytak az életek!", 48, (255, 92, 120), "black", center=(W // 2, top + 200), outline=theme.WHITE)
            text(surf, "Semmi baj, a pingvinek újra elbújnak.", 26, theme.TEXT, "medium", center=(W // 2, top + 252))
            text(surf, "Próbáld meg egy új pályán!", 26, theme.TEXT, "medium", center=(W // 2, top + 288))
        super().draw(surf)


class ScoresScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.buttons = [Button((W // 2 - 120, H - 92, 240, 62), "Vissza", theme.BTN_PINK,
                               action=lambda: app.goto(MenuScene(app)))]

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.app.goto(MenuScene(self.app))
            return True
        return super().handle(event)

    def draw(self, surf):
        rainbow_title(surf, "Dicsőségtábla", 64, (W // 2, 64), self.t, wave=3)
        data = self.app.store.data
        cols = [("Legjobb játékok", [(f"{e['total']} pont", f"{e['level']}. szintig", e["date"]) for e in data["highscores"]]),
                ("Legjobb pályák", [(f"{e['score']} pont", f"{e['level']}. szint · {e['size']}×{e['size']} · {fmt_time(e['seconds'])}",
                                     e["date"]) for e in data["best_levels"]])]
        run = self.app.store.run
        for i, (title, rows) in enumerate(cols):
            x = 40 + i * 482
            card(surf, (x, 116, 462, 476), radius=28)
            text(surf, title, 30, theme.TEXT, "black", center=(x + 231, 148))
            if not rows:
                text(surf, "Még nincs eredmény – irány játszani!", 22, theme.TEXT_SOFT, "medium", center=(x + 231, 300))
            for j, (a, b, d) in enumerate(rows[:10]):
                y = 196 + j * 40
                medal = [(255, 200, 40), (190, 196, 214), (230, 150, 90)]
                pygame.draw.circle(surf, medal[j] if j < 3 else (234, 226, 248), (x + 34, y), 15)
                text(surf, str(j + 1), 20, theme.WHITE if j < 3 else theme.TEXT_SOFT, "black", center=(x + 34, y + 1))
                text(surf, a, 24, theme.TEXT, "bold", midleft=(x + 60, y))
                text(surf, b, 18, theme.TEXT_SOFT, "medium", midleft=(x + 190, y))
        if run:
            text(surf, f"Jelenlegi játék: {run['level']}. szint, {run['total']} pont", 22, theme.TEXT_SOFT, "medium",
                 center=(W // 2, 612))
        super().draw(surf)


class HelpScene(Scene):
    music = None
    LINES = [
        ("A cél", "Rejts el pontosan egy pingvint minden sorba, minden oszlopba és minden színes területre."),
        ("A szabály", "Két pingvin soha nem érhet egymáshoz – még átlósan sem!"),
        ("Egér", "Bal klikk: üres → X → pingvin → üres.  Jobb klikk: X be/ki.  Húzással sok X."),
        ("Életek", "Pályánként 3 életed van. Rossz helyre tett pingvin egy életbe kerül. Az X ingyenes."),
        ("Tippek", "Egy tipp felfed egy helyes pingvint. Minden megmaradt életed +1 tipp a következő pályára."),
        ("Tipp-korlát", "Egyszerre legfeljebb (elrejtett pingvinek száma − 2) tipped lehet."),
        ("Pontok", "Gyorsaság, a pálya mérete és a megmaradt életek növelik, a tippek csökkentik."),
        ("Billentyűk", "Nyilak, Szóköz, X, P, H: tipp, M: zene be/ki, S: hangok be/ki, F11, Esc."),
    ]

    def __init__(self, app, back: Scene | None = None):
        super().__init__(app)
        self.back = back
        self.buttons = [Button((W // 2 - 120, H - 82, 240, 60), "Értem!", theme.BTN_MINT, action=self.leave)]

    def leave(self):
        self.app.goto(self.back or MenuScene(self.app))

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.leave()
            return True
        return super().handle(event)

    def draw(self, surf):
        rainbow_title(surf, "Hogyan játssz?", 60, (W // 2, 54), self.t, wave=3)
        card(surf, (40, 100, W - 80, 524), radius=28)
        y = 128
        colors = theme.TITLE_COLORS
        for i, (head, body) in enumerate(self.LINES):
            col = colors[i % len(colors)]
            pygame.draw.circle(surf, col, (80, y + 13), 12)
            text(surf, head, 24, col, "black", midleft=(104, y + 13))
            text(surf, body, 20, theme.TEXT, "medium", midleft=(104, y + 41))
            y += 61
        img = image("penguins/penguin_happy.png", 110)
        surf.blit(img, img.get_rect(bottomright=(W - 56, 616 + math.sin(self.t * 3) * 4)))
        super().draw(surf)


class SettingsScene(Scene):
    """Music / effects volume + mute, auto-X and fullscreen toggles."""
    music = None

    def __init__(self, app, back: Scene | None = None):
        super().__init__(app)
        self.back = back
        a = app.audio
        x0 = 330
        self.music_slider = Slider((x0, 200, 400, 18), a.music_volume, theme.BTN_MINT, self._music_vol)
        self.sfx_slider = Slider((x0, 300, 400, 18), a.sfx_volume, theme.BTN_BLUE, self._sfx_vol)
        self.sliders = [self.music_slider, self.sfx_slider]
        self.music_btn = IconButton((800, 209), "icons/music.png", theme.BTN_MINT, app.toggle_music, 56, "M")
        self.sfx_btn = IconButton((800, 309), "icons/speaker.png", theme.BTN_BLUE, app.toggle_sfx, 56, "S")
        self.autox_btn = Button((x0 - 10, 380, 420, 58), "", theme.BTN_BLUE, size=26, action=self._auto_x)
        self.fs_btn = Button((x0 - 10, 456, 420, 58), "", theme.BTN_PURPLE, size=26, action=app.toggle_fullscreen)
        self.buttons = [self.music_btn, self.sfx_btn, self.autox_btn, self.fs_btn,
                        Button((W // 2 - 120, H - 108, 240, 62), "Kész", theme.BTN_PINK, action=self.leave)]

    def _music_vol(self, v):
        self.app.audio.set_music_volume(v)
        self.app.store.save()

    def _sfx_vol(self, v):
        self.app.audio.set_sfx_volume(v)
        self.app.audio.play("mark")
        self.app.store.save()

    def _auto_x(self):
        s = self.app.store.data["settings"]
        s["auto_x"] = not s["auto_x"]
        if isinstance(self.back, PlayScene) and self.back.state:
            self.back.state.auto_x = s["auto_x"]
        self.app.store.save()

    def leave(self):
        self.app.store.save()
        self.app.goto(self.back or MenuScene(self.app))

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
            self.leave()
            return True
        for sl in self.sliders:
            if sl.handle(event):
                return True
        return super().handle(event)

    def update(self, dt):
        super().update(dt)
        a, st = self.app.audio, self.app.store.data["settings"]
        self.music_slider.value = a.music_volume
        self.sfx_slider.value = a.sfx_volume
        self.music_btn.icon = "icons/music_off.png" if a.music_muted else "icons/music.png"
        self.music_btn.colors = theme.BTN_GREY if a.music_muted else theme.BTN_MINT
        self.sfx_btn.icon = "icons/speaker_off.png" if a.sfx_muted else "icons/speaker.png"
        self.sfx_btn.colors = theme.BTN_GREY if a.sfx_muted else theme.BTN_BLUE
        self.autox_btn.label = "Automatikus X: " + ("BE" if st["auto_x"] else "KI")
        self.autox_btn.colors = theme.BTN_BLUE if st["auto_x"] else theme.BTN_GREY
        self.fs_btn.label = "Teljes képernyő: " + ("BE" if st.get("fullscreen") else "KI")
        self.fs_btn.colors = theme.BTN_PURPLE if st.get("fullscreen") else theme.BTN_GREY

    def draw(self, surf):
        rainbow_title(surf, "Beállítások", 64, (W // 2, 70), self.t, wave=3)
        card(surf, (150, 136, W - 300, 412), radius=30)
        a = self.app.audio
        for label, sl, muted, y in (("Zene", self.music_slider, a.music_muted, 209),
                                    ("Hangok", self.sfx_slider, a.sfx_muted, 309)):
            text(surf, label, 30, theme.TEXT, "black", midleft=(190, y))
            sl.draw(surf, dim=muted)
            pct = "némítva" if muted else f"{int(round(sl.value * 100))} %"
            text(surf, pct, 20, theme.TEXT_SOFT, "medium", center=(sl.rect.centerx, y + 34))
        if not a.available:
            text(surf, "Nem található hangeszköz – a játék hang nélkül fut.", 20, (255, 92, 120), "bold",
                 center=(W // 2, 160))
        super().draw(surf)
        text(surf, "M: zene be/ki   ·   S: hangok be/ki   ·   F11: teljes képernyő", 20, theme.TEXT_SOFT, "medium",
             center=(W // 2, H - 26))


# ======================================================================= app
class App:
    def __init__(self, headless: bool = False, fullscreen: bool | None = None, audio: bool = True):
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.display.init()   # no mixer: the game is silent, avoids audio-device warnings
        pygame.font.init()
        pygame.display.set_caption("Tuxdoku")
        try:
            pygame.display.set_icon(pygame.image.load(str(icon_path())))
        except pygame.error:
            pass
        self.store = Store()
        self.audio = Audio(self.store.data["settings"], enable=audio)
        Button.on_hover = lambda: self.audio.play("hover")
        Button.on_click = lambda: self.audio.play("click")
        fs = self.store.data["settings"].get("fullscreen", False) if fullscreen is None else fullscreen
        self.screen = self._set_mode(fs)
        self.clock = pygame.time.Clock()
        self.factory = PuzzleFactory()
        self.snow = Snow()
        self.scene: Scene = MenuScene(self)
        self.audio.play_music(self.scene.music)
        self.running = True
        self._palettes: dict[int, list] = {}

    def _set_mode(self, fullscreen: bool):
        flags = pygame.SCALED | (pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE)
        try:
            return pygame.display.set_mode((W, H), flags)
        except pygame.error:
            return pygame.display.set_mode((W, H))

    def region_palette(self, puzzle: Puzzle):
        key = id(puzzle)
        if key not in self._palettes:
            rng = random.Random(puzzle.seed or 0)
            cols = theme.REGION_COLORS[:]
            rng.shuffle(cols)
            self._palettes = {key: cols[: puzzle.size]}
        return self._palettes[key]

    # ------------------------------------------------------------ flow
    def goto(self, scene: Scene):
        self.scene = scene
        if scene.music:
            self.audio.play_music(scene.music)

    def toggle_music(self):
        self.audio.toggle_music()
        self.store.save()

    def toggle_sfx(self):
        self.audio.toggle_sfx()
        self.store.save()

    def new_game(self):
        run = self.store.run
        if run:
            self.store.finish_run(run["total"], run["level"])
        self.store.set_run(1, 0, rules.STARTING_HINTS)
        self.goto(PlayScene(self, 1, 0, rules.STARTING_HINTS))

    def continue_game(self):
        run = self.store.run or {"level": 1, "total": 0, "hints": rules.STARTING_HINTS}
        self.goto(PlayScene(self, run["level"], run["total"], run["hints"]))

    def level_won(self, play: PlayScene):
        st = play.state
        bd = st.score()
        next_level = play.level + 1
        next_size = rules.level_spec(next_level).size
        new_hints = rules.hints_after_level(st.hints, st.lives, next_size)
        gained = st.lives
        play.total += bd.total
        self.store.record_level(bd.total, play.level, play.n, st.elapsed)
        self.store.update_best_total(play.total)
        self.store.set_run(next_level, play.total, new_hints)
        play.overlay = ResultOverlay(self, play, True, bd, new_hints, gained)

    def level_lost(self, play: PlayScene):
        # the bank goes back to what it was when the level started
        self.store.set_run(play.level, play.total, play.state.hints_at_start)
        play.overlay = ResultOverlay(self, play, False)

    def next_level(self):
        run = self.store.run
        self.goto(PlayScene(self, run["level"], run["total"], run["hints"]))

    def retry_level(self):
        self.continue_game()

    def toggle_fullscreen(self):
        s = self.store.data["settings"]
        s["fullscreen"] = not s.get("fullscreen", False)
        self.store.save()
        try:
            pygame.display.toggle_fullscreen()
        except pygame.error:
            self.screen = self._set_mode(s["fullscreen"])

    def quit(self):
        self.running = False

    # ------------------------------------------------------------ loop
    def step(self, dt: float, events=()):
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                self.toggle_fullscreen()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                self.toggle_music()
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_s, pygame.K_n):
                self.toggle_sfx()
            else:
                self.scene.handle(event)
        self.audio.update(dt)
        self.snow.update(dt)
        self.scene.update(dt)
        draw_background(self.screen, self.snow)
        self.scene.draw(self.screen)

    def run(self):
        while self.running:
            dt = min(self.clock.tick(theme.FPS) / 1000.0, 0.1)
            self.step(dt, pygame.event.get())
            pygame.display.flip()
        self.store.save()
        self.factory.shutdown()
        self.audio.shutdown()
        pygame.quit()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tuxdoku", description="Tuxdoku – pingvines logikai játék")
    parser.add_argument("--fullscreen", action="store_true", help="teljes képernyő")
    parser.add_argument("--mute", action="store_true", help="hang nélkül (nem nyitja meg a hangeszközt)")
    parser.add_argument("--version", action="version", version=f"Tuxdoku {__version__}")
    args = parser.parse_args(argv)
    App(fullscreen=True if args.fullscreen else None, audio=not args.mute).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
