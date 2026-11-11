"""Small drawing helpers and widgets: gradient background, cards, buttons, particles."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from . import theme
from .resources import font, image


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def mix(c1, c2, t: float):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def ease_out_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


_GRADIENT: dict[tuple, pygame.Surface] = {}


def gradient(size, top, bottom) -> pygame.Surface:
    key = (size, top, bottom)
    if key not in _GRADIENT:
        w, h = size
        col = pygame.Surface((1, h))
        for y in range(h):
            col.set_at((0, y), mix(top, bottom, y / max(1, h - 1)))
        _GRADIENT[key] = pygame.transform.smoothscale(col, (w, h)) if w > 1 else col
    return _GRADIENT[key]


def card(surf, rect, color=theme.CARD, radius=22, border=theme.CARD_BORDER, shadow=6, alpha=255):
    rect = pygame.Rect(rect)
    if shadow:
        sh = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(sh, (*theme.SHADOW, 90), sh.get_rect(), border_radius=radius)
        surf.blit(sh, rect.move(0, shadow))
    if alpha < 255:
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (*color, alpha), s.get_rect(), border_radius=radius)
        surf.blit(s, rect)
    else:
        pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, border, rect, 3, border_radius=radius)


def text(surf, msg, size, color=theme.TEXT, weight="bold", center=None, topleft=None, midleft=None,
         midright=None, shadow: tuple | None = None, outline: tuple | None = None, outline_w=2):
    f = font(size, weight)
    img = f.render(msg, True, color)
    rect = img.get_rect()
    if center is not None:
        rect.center = center
    elif topleft is not None:
        rect.topleft = topleft
    elif midleft is not None:
        rect.midleft = midleft
    elif midright is not None:
        rect.midright = midright
    if outline:
        o = f.render(msg, True, outline)
        for dx in range(-outline_w, outline_w + 1):
            for dy in range(-outline_w, outline_w + 1):
                if dx * dx + dy * dy <= outline_w * outline_w + 1:
                    surf.blit(o, rect.move(dx, dy))
    if shadow:
        surf.blit(f.render(msg, True, shadow), rect.move(0, 3))
    surf.blit(img, rect)
    return rect


def rainbow_title(surf, msg, size, center, t=0.0, wave=6):
    """Each letter a different cheerful colour, gently bouncing."""
    f = font(size, "black")
    widths = [f.size(ch)[0] for ch in msg]
    total = sum(widths)
    x = center[0] - total / 2
    for i, ch in enumerate(msg):
        color = theme.TITLE_COLORS[i % len(theme.TITLE_COLORS)]
        dy = math.sin(t * 3 + i * 0.7) * wave
        cx = x + widths[i] / 2
        text(surf, ch, size, color, "black", center=(cx, center[1] + dy), outline=theme.WHITE,
             outline_w=4, shadow=None)
        x += widths[i]


class Button:
    # global hooks (set by the App) used for UI sounds
    on_hover = None
    on_click = None

    def __init__(self, rect, label, colors=theme.BTN_BLUE, icon: str | None = None, size=30,
                 action=None, key=None, radius=18, tooltip: str | None = None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.colors = colors
        self.icon = icon
        self.size = size
        self.action = action
        self.key = key
        self.hover = False
        self.pressed = False
        self.enabled = True
        self.radius = radius
        self.tooltip = tooltip
        self._lift = 0.0

    def handle(self, event) -> bool:
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            was = self.hover
            self.hover = self.rect.collidepoint(event.pos)
            if self.hover and not was and Button.on_hover:
                Button.on_hover()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self.pressed = True
            return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            hit = self.pressed and self.rect.collidepoint(event.pos)
            self.pressed = False
            if hit and self.action:
                if Button.on_click:
                    Button.on_click()
                self.action()
                return True
        return False

    def update(self, dt):
        target = 3.0 if self.hover and self.enabled else 0.0
        self._lift += (target - self._lift) * min(1.0, dt * 14)

    def draw(self, surf):
        face, edge = self.colors if self.enabled else theme.BTN_GREY
        depth = 6
        r = self.rect.move(0, -int(self._lift) + (3 if self.pressed else 0))
        rad = self.radius
        pygame.draw.rect(surf, (*theme.SHADOW,), self.rect.move(0, depth + 2), border_radius=rad)
        pygame.draw.rect(surf, edge, r.move(0, depth), border_radius=rad)
        pygame.draw.rect(surf, mix(face, theme.WHITE, 0.18) if self.hover else face, r, border_radius=rad)
        # glossy highlight
        inset = 8 if rad < r.h // 2 else r.w // 5
        gl = pygame.Surface((r.w - 2 * inset, r.h // 2 - 4), pygame.SRCALPHA)
        pygame.draw.rect(gl, (255, 255, 255, 70), gl.get_rect(), border_radius=min(12, gl.get_height() // 2))
        surf.blit(gl, (r.x + inset, r.y + 4))
        cx = r.centerx
        if self.icon:
            ic = image(self.icon, int(r.h * (0.62 if self.label else 0.58)))
            lw = font(self.size).size(self.label)[0] if self.label else 0
            gap = 10 if self.label else 0
            x0 = cx - (ic.get_width() + gap + lw) // 2
            surf.blit(ic, (x0, r.centery - ic.get_height() // 2))
            if self.label:
                text(surf, self.label, self.size, theme.WHITE, center=(x0 + ic.get_width() + gap + lw / 2, r.centery + 2),
                     outline=edge, outline_w=2)
        else:
            text(surf, self.label, self.size, theme.WHITE, center=(cx, r.centery + 2), outline=edge, outline_w=2)


class IconButton(Button):
    """Small round button showing only an icon (speaker, music, gear, ...)."""

    def __init__(self, center, icon, colors=theme.BTN_BLUE, action=None, size=52, tooltip=None):
        rect = pygame.Rect(0, 0, size, size)
        rect.center = center
        super().__init__(rect, "", colors, icon=icon, action=action, radius=size // 2, tooltip=tooltip)

    def draw(self, surf):
        super().draw(surf)
        if self.hover and self.tooltip:
            f = font(18, "bold")
            w = f.size(self.tooltip)[0] + 20
            tip = pygame.Rect(0, 0, w, 30)
            tip.midbottom = (self.rect.centerx, self.rect.top - 6)
            tip.clamp_ip(surf.get_rect())
            pygame.draw.rect(surf, theme.TEXT, tip, border_radius=10)
            text(surf, self.tooltip, 18, theme.WHITE, center=(tip.centerx, tip.centery + 1))


class Slider:
    """Horizontal 0..1 slider operated by click / drag (and arrow keys when focused by the scene)."""

    def __init__(self, rect, value=0.5, colors=theme.BTN_PINK, on_change=None):
        self.rect = pygame.Rect(rect)
        self.value = max(0.0, min(1.0, value))
        self.colors = colors
        self.on_change = on_change
        self.dragging = False
        self.enabled = True

    def _set_from_x(self, x):
        v = (x - self.rect.x) / max(1, self.rect.w)
        v = round(max(0.0, min(1.0, v)) * 20) / 20          # 5 % steps
        if v != self.value:
            self.value = v
            if self.on_change:
                self.on_change(v)

    def handle(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.inflate(24, 30).collidepoint(event.pos):
            self.dragging = True
            self._set_from_x(event.pos[0])
            return True
        if event.type == pygame.MOUSEMOTION and self.dragging:
            self._set_from_x(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging:
            self.dragging = False
            return True
        return False

    def update(self, dt):
        pass

    def draw(self, surf, dim=False):
        face, edge = theme.BTN_GREY if dim else self.colors
        r = self.rect
        pygame.draw.rect(surf, (236, 228, 248), r, border_radius=r.h // 2)
        filled = r.copy()
        filled.w = max(r.h, int(r.w * self.value))
        pygame.draw.rect(surf, face, filled, border_radius=r.h // 2)
        kx = r.x + int(r.w * self.value)
        pygame.draw.circle(surf, theme.SHADOW, (kx, r.centery + 3), r.h)
        pygame.draw.circle(surf, theme.WHITE, (kx, r.centery), r.h)
        pygame.draw.circle(surf, edge, (kx, r.centery), r.h, 4)


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: tuple
    life: float
    size: float
    spin: float = 0.0
    angle: float = 0.0
    kind: str = "confetti"
    age: float = 0.0


class Particles:
    def __init__(self):
        self.items: list[Particle] = []

    def confetti(self, x, y, count=80, spread=420):
        for _ in range(count):
            a = random.uniform(-math.pi, 0)
            sp = random.uniform(spread * 0.4, spread)
            self.items.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp, random.choice(theme.CONFETTI),
                                       random.uniform(1.6, 3.0), random.uniform(6, 12), random.uniform(-8, 8),
                                       random.uniform(0, 6.28)))

    def rain(self, x, y=-12):
        self.items.append(Particle(x, y, random.uniform(-30, 30), random.uniform(60, 170), random.choice(theme.CONFETTI),
                                   random.uniform(3.0, 4.5), random.uniform(6, 11), random.uniform(-8, 8),
                                   random.uniform(0, 6.28)))

    def sparkle(self, x, y, count=14, color=theme.HINT_GLOW):
        for i in range(count):
            a = i / count * math.tau + random.uniform(-0.2, 0.2)
            sp = random.uniform(80, 200)
            self.items.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp, color, random.uniform(0.5, 0.9),
                                       random.uniform(4, 8), kind="spark"))

    def update(self, dt):
        for p in self.items:
            p.age += dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.kind == "confetti":
                p.vy += 520 * dt
                p.vx *= 0.99
            else:
                p.vx *= 0.9
                p.vy *= 0.9
            p.angle += p.spin * dt
        self.items = [p for p in self.items if p.age < p.life]

    def draw(self, surf):
        for p in self.items:
            fade = 1 - p.age / p.life
            if p.kind == "confetti":
                w = p.size * abs(math.cos(p.angle)) + 2
                rect = pygame.Rect(0, 0, w, p.size * 0.6 + 2)
                rect.center = (p.x, p.y)
                pygame.draw.rect(surf, p.color, rect, border_radius=2)
            else:
                pygame.draw.circle(surf, mix(theme.WHITE, p.color, fade), (int(p.x), int(p.y)), max(1, int(p.size * fade)))


class Snow:
    """Slowly drifting snowflakes / bubbles for the background."""

    def __init__(self, count=26, seed=3):
        rng = random.Random(seed)
        self.flakes = [[rng.uniform(0, theme.WIDTH), rng.uniform(0, theme.HEIGHT), rng.uniform(14, 34),
                        rng.uniform(12, 30), rng.uniform(0, 6.28), rng.choice([0, 1, 1, 2])] for _ in range(count)]

    def update(self, dt):
        for f in self.flakes:
            f[1] += f[3] * dt
            f[4] += dt
            if f[1] > theme.HEIGHT + 40:
                f[1] = -40
                f[0] = random.uniform(0, theme.WIDTH)

    def draw(self, surf):
        for x, y, s, _sp, ph, kind in self.flakes:
            xx = x + math.sin(ph) * 14
            if kind == 0:
                img = image("icons/snowflake.png", int(s))
                surf.blit(img, (xx - s / 2, y - s / 2))
            else:
                c = theme.TITLE_COLORS[int(s) % len(theme.TITLE_COLORS)]
                bub = pygame.Surface((int(s), int(s)), pygame.SRCALPHA)
                pygame.draw.circle(bub, (*c, 46), (int(s) // 2, int(s) // 2), int(s) // 2)
                pygame.draw.circle(bub, (255, 255, 255, 120), (int(s * 0.35), int(s * 0.35)), max(2, int(s * 0.12)))
                surf.blit(bub, (xx - s / 2, y - s / 2))


def draw_background(surf, snow: Snow | None = None):
    surf.blit(gradient(surf.get_size(), theme.BG_TOP, theme.BG_BOTTOM), (0, 0))
    if snow:
        snow.draw(surf)


def fmt_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"
