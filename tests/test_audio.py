import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from tuxdoku import audio as audio_mod  # noqa: E402
from tuxdoku.audio import MUSIC_TRACKS, SOUND_NAMES, Audio  # noqa: E402
from tuxdoku.resources import ASSETS  # noqa: E402
from tuxdoku.storage import Store  # noqa: E402


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TUXDOKU_DATA_DIR", str(tmp_path))
    yield
    if pygame.mixer.get_init():
        pygame.mixer.quit()


def test_audio_assets_exist_and_are_small():
    total = 0
    for name in SOUND_NAMES:
        p = ASSETS / "sounds" / f"{name}.wav"
        assert p.is_file()
        total += p.stat().st_size
    for rel in MUSIC_TRACKS.values():
        p = ASSETS / rel
        assert p.is_file() and p.read_bytes()[:4] == b"OggS"
        total += p.stat().st_size
    assert total < 5 * 1024 * 1024


def test_default_audio_settings_present():
    st = Store()
    for key in ("music_volume", "sfx_volume", "music_muted", "sfx_muted"):
        assert key in st.data["settings"]


def test_audio_settings_persist(tmp_path):
    st = Store(tmp_path / "p.json")
    a = Audio(st.data["settings"], enable=False)
    a.set_music_volume(0.3)
    a.set_sfx_volume(1.7)                 # clamped
    a.toggle_music()
    a.toggle_sfx()
    st.save()
    again = Store(tmp_path / "p.json").data["settings"]
    assert again["music_volume"] == 0.3
    assert again["sfx_volume"] == 1.0
    assert again["music_muted"] is True and again["sfx_muted"] is True
    b = Audio(again, enable=False)
    b.toggle_music()
    assert b.music_muted is False


def test_old_save_without_audio_keys_gets_defaults(tmp_path):
    p = tmp_path / "p.json"
    p.write_text('{"settings": {"auto_x": false}}', encoding="utf-8")
    s = Store(p).data["settings"]
    assert s["auto_x"] is False and s["music_volume"] == 0.5 and s["sfx_muted"] is False


def test_no_audio_device_runs_silently(monkeypatch):
    def boom(*a, **k):
        raise pygame.error("No available audio device")

    monkeypatch.setattr(audio_mod.pygame.mixer, "init", boom)
    monkeypatch.setattr(audio_mod.pygame.mixer, "get_init", lambda: None)
    a = Audio({}, enable=True)
    assert a.available is False and a.sounds == {}
    a.play("place")
    a.play_music("menu")
    a.play_music("game")
    a.toggle_music()
    a.toggle_sfx()
    a.set_music_volume(0.4)
    a.duck(1.0)
    a.update(2.0)
    a.shutdown()


def test_app_starts_and_plays_without_audio(monkeypatch):
    def boom(*a, **k):
        raise pygame.error("No available audio device")

    monkeypatch.setattr(audio_mod.pygame.mixer, "init", boom)
    monkeypatch.setattr(audio_mod.pygame.mixer, "get_init", lambda: None)
    from tuxdoku.app import App, PlayScene

    app = App(headless=True)
    assert not app.audio.available
    scene = PlayScene(app, 1, 0, 1, seed=1)
    app.goto(scene)
    scene.future.result()
    app.step(1 / 60)
    cell = sorted(scene.state.puzzle.solution_cells())[0]
    scene.act(cell, "place")
    scene.hint()
    for key in (pygame.K_m, pygame.K_s):
        app.step(1 / 60, [pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)])
    assert app.audio.music_muted and app.audio.sfx_muted


def test_dummy_driver_loads_everything():
    a = Audio({}, enable=True)
    if not a.available:
        pytest.skip("SDL dummy audio driver unavailable")
    assert set(a.sounds) == set(SOUND_NAMES)
    a.play("fanfare")
    a.play_music("menu")
    assert a.track == "menu"
    a.play_music("game")
    assert a.track == "game"
    a.shutdown()


def test_keyboard_shortcuts_toggle_audio():
    from tuxdoku.app import App

    app = App(headless=True)
    ev = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)  # noqa: E731
    app.step(1 / 60, [ev(pygame.K_m)])
    assert app.audio.music_muted
    app.step(1 / 60, [ev(pygame.K_n)])
    assert app.audio.sfx_muted
    app.step(1 / 60, [ev(pygame.K_m), ev(pygame.K_s)])
    assert not app.audio.music_muted and not app.audio.sfx_muted
    assert Store().data["settings"]["music_muted"] is False
