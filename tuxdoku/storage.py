"""Persist progress, settings and high scores as JSON.

Location: $TUXDOKU_DATA_DIR, else $XDG_DATA_HOME/tuxdoku, else ~/.local/share/tuxdoku
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

MAX_HIGHSCORES = 10


def data_dir() -> Path:
    env = os.environ.get("TUXDOKU_DATA_DIR")
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "tuxdoku"


def default_save() -> dict:
    return {
        "version": 1,
        "run": None,            # {"level", "total", "hints"} of the game in progress
        "best_total": 0,
        "highest_level": 0,
        "highscores": [],       # [{"total", "level", "date"}] finished runs
        "best_levels": [],      # [{"score", "level", "size", "seconds", "date"}]
        "settings": {"auto_x": True, "fullscreen": False, "music_volume": 0.5, "sfx_volume": 0.8,
                     "music_muted": False, "sfx_muted": False},
    }


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "progress.json"
        self.data = default_save()
        self.load()

    def load(self) -> None:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                base = default_save()
                base.update(loaded)
                base["settings"] = {**default_save()["settings"], **(loaded.get("settings") or {})}
                self.data = base
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    # -- run -------------------------------------------------------------
    @property
    def run(self) -> dict | None:
        return self.data.get("run")

    def set_run(self, level: int, total: int, hints: int) -> None:
        self.data["run"] = {"level": level, "total": total, "hints": hints}
        self.data["highest_level"] = max(self.data.get("highest_level", 0), level)
        self.save()

    def record_level(self, score: int, level: int, size: int, seconds: float) -> bool:
        """Store a level result; returns True if it entered the top list."""
        entry = {"score": score, "level": level, "size": size, "seconds": round(seconds),
                 "date": time.strftime("%Y-%m-%d")}
        lst = self.data.setdefault("best_levels", [])
        lst.append(entry)
        lst.sort(key=lambda e: -e["score"])
        del lst[MAX_HIGHSCORES:]
        return entry in lst

    def finish_run(self, total: int, level: int) -> bool:
        """Close the current run (new game started); returns True if it is a top run."""
        if total <= 0:
            return False
        entry = {"total": total, "level": level, "date": time.strftime("%Y-%m-%d")}
        lst = self.data.setdefault("highscores", [])
        lst.append(entry)
        lst.sort(key=lambda e: -e["total"])
        del lst[MAX_HIGHSCORES:]
        self.save()
        return entry in lst

    def update_best_total(self, total: int) -> None:
        self.data["best_total"] = max(self.data.get("best_total", 0), total)
