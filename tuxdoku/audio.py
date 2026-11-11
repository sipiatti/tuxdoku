"""Sound effects and background music.

Everything degrades gracefully: if ``pygame.mixer`` cannot be initialised
(no audio device, missing SDL_mixer, ...) or a file is missing, the game
simply runs silently.
"""
from __future__ import annotations

import pygame

from .resources import ASSETS

SOUND_NAMES = ("click", "hover", "mark", "unmark", "place", "wrong", "hint", "fanfare", "gameover")
MUSIC_TRACKS = {"menu": "music/menu.ogg", "game": "music/game.ogg"}

DEFAULT_AUDIO_SETTINGS = {
    "music_volume": 0.5,
    "sfx_volume": 0.8,
    "music_muted": False,
    "sfx_muted": False,
}


def clamp01(v) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


class Audio:
    def __init__(self, settings: dict, enable: bool = True):
        """``settings`` is the (persisted) settings dict; it is read and updated in place."""
        self.settings = settings
        for k, v in DEFAULT_AUDIO_SETTINGS.items():
            settings.setdefault(k, v)
        self.available = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.track: str | None = None
        self._duck = 0.0
        if enable:
            self._init_mixer()

    # ------------------------------------------------------------ setup
    def _init_mixer(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 512)
                pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
            self.available = True
        except Exception:          # pygame.error, NotImplementedError (no SDL_mixer), ...
            self.available = False
            return
        for name in SOUND_NAMES:
            try:
                self.sounds[name] = pygame.mixer.Sound(str(ASSETS / "sounds" / f"{name}.wav"))
            except Exception:
                pass

    # ------------------------------------------------------------ settings
    @property
    def music_volume(self) -> float:
        return clamp01(self.settings["music_volume"])

    @property
    def sfx_volume(self) -> float:
        return clamp01(self.settings["sfx_volume"])

    @property
    def music_muted(self) -> bool:
        return bool(self.settings["music_muted"])

    @property
    def sfx_muted(self) -> bool:
        return bool(self.settings["sfx_muted"])

    def set_music_volume(self, v: float) -> None:
        self.settings["music_volume"] = round(clamp01(v), 2)
        if self.settings["music_volume"] > 0 and self.music_muted:
            self.settings["music_muted"] = False
            self._restart_music()
        self._apply_music_volume()

    def set_sfx_volume(self, v: float) -> None:
        self.settings["sfx_volume"] = round(clamp01(v), 2)
        if self.settings["sfx_volume"] > 0:
            self.settings["sfx_muted"] = False

    def toggle_music(self) -> bool:
        self.settings["music_muted"] = not self.music_muted
        if self.music_muted:
            self._stop_music()
        else:
            self._restart_music()
        return not self.music_muted

    def toggle_sfx(self) -> bool:
        self.settings["sfx_muted"] = not self.sfx_muted
        if not self.sfx_muted:
            self.play("click")
        return not self.sfx_muted

    # ------------------------------------------------------------- effects
    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.available or self.sfx_muted or self.sfx_volume <= 0:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        try:
            snd.set_volume(clamp01(self.sfx_volume * volume))
            snd.play()
        except Exception:
            pass

    # --------------------------------------------------------------- music
    def play_music(self, track: str) -> None:
        """Switch the looping background track ("menu" / "game"); no-op if already playing."""
        if track == self.track:
            return
        self.track = track
        if not self.music_muted:
            self._restart_music()

    def duck(self, seconds: float = 2.5) -> None:
        """Temporarily lower the music (e.g. under the fanfare)."""
        self._duck = max(self._duck, seconds)
        self._apply_music_volume()

    def update(self, dt: float) -> None:
        if self._duck > 0:
            self._duck = max(0.0, self._duck - dt)
            if self._duck == 0:
                self._apply_music_volume()

    def _apply_music_volume(self) -> None:
        if not self.available:
            return
        try:
            v = self.music_volume * (0.25 if self._duck > 0 else 1.0)
            pygame.mixer.music.set_volume(0.0 if self.music_muted else v)
        except Exception:
            pass

    def _restart_music(self) -> None:
        if not self.available or not self.track:
            return
        try:
            pygame.mixer.music.load(str(ASSETS / MUSIC_TRACKS[self.track]))
            self._apply_music_volume()
            pygame.mixer.music.play(loops=-1, fade_ms=700)
        except Exception:
            pass

    def _stop_music(self) -> None:
        if not self.available:
            return
        try:
            pygame.mixer.music.fadeout(300)
        except Exception:
            pass

    def shutdown(self) -> None:
        if self.available:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except Exception:
                pass
