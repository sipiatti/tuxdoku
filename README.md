# Tuxdoku 🐧

*[English below](#english)*

Vidám, pasztellszínű logikai játék pingvinekkel, Python 3 + pygame alapon.

> **Szerző:** Siposs Attila <sipiatti@gmail.com>  
> A játék *vibe coding* technikával, a **Grok Bot** segítségével készült.

## Szabályok

Az N×N-es tábla N darab színes területre van osztva. Rejts el **pontosan N pingvint** úgy, hogy

* minden **sorban**, minden **oszlopban** és minden **színes területen** pontosan egy pingvin legyen,
* két pingvin **ne érjen egymáshoz**, még átlósan sem.

Minden pályának pontosan egy megoldása van (a generátor egy megoldóval ellenőrzi).

## Irányítás

| Egér / billentyű | Hatás |
|---|---|
| Bal klikk | üres → X → pingvin → üres |
| Jobb klikk | X jel be/ki |
| Húzás (bal gomb üres mezőről, vagy jobb gomb) | sok X egyszerre (vagy törlés) |
| Nyilak, Szóköz/Enter | kurzor mozgatása, léptetés |
| X / P / Backspace | X jel / pingvin / törlés a kurzornál |
| H | tipp |
| M | zene be/ki |
| S (vagy N) | hangeffektek be/ki |
| Esc | menü |
| F11 | teljes képernyő |

* **Életek:** pályánként 3. Ha a pingvin nem a megoldás része, egy életbe kerül (a mező X-re vált). Az X jelek ingyenesek. 0 életnél a pálya elveszett, újrapróbálhatod egy új pályán.
* **Tippek:** egy tipp felfed egy helyes pingvint (és automatikusan X-eli a kizárt mezőket). Minden megmaradt élet +1 tipp a következő pályára. Egyszerre legfeljebb **N − 2** tipped lehet (N = elrejtett pingvinek száma).
* **Automatikus X:** a menüből/oldalsávból kapcsolható; egy helyes pingvin után kis pöttyökkel jelöli a kizárt mezőket.
* **Szintek:** 1–3: 5×5, 4–6: 6×6, 7–9: 7×7, 10–12: 8×8, 13–15: 9×9, 16-tól: 10×10. Egy méreten belül a későbbi szintek trükkösebb pályát választanak.
* **Pontozás:** méret, gyorsaság, megmaradt életek, felhasznált tippek (lásd lent).
* **Hang:** vidám hangeffektek (X jel, pingvin, hiba, tipp, győzelmi fanfár, vereség, gombok) és két ismétlődő háttérzene (menü és játék). A ⚙ **Beállítások** képernyőn (a menü jobb felső sarkában és játék közben a jobb alsó ikonsorban) külön állítható a zene és az effektek hangereje, és mindkettő némítható; a hangszóró/hangjegy ikonok és az M / S billentyűk gyors némításra valók. Ha nincs hangeszköz, a játék egyszerűen hang nélkül fut (`--mute` kapcsolóval a hangeszközt meg sem nyitja).
* A haladás, a beállítások és a dicsőségtábla helye: `~/.local/share/tuxdoku/progress.json` (vagy `$XDG_DATA_HOME/tuxdoku`).

## Futtatás

```bash
sudo apt install python3-pygame      # vagy: pip install -r requirements.txt
python3 -m tuxdoku                   # a projekt mappájából
# vagy telepítve:
pip install .  &&  tuxdoku
```

Tesztek: `python3 -m pytest`

### Debian/Ubuntu csomag (.deb)

```bash
packaging/build_deb.sh                 # -> dist/tuxdoku_0.2.0_all.deb
sudo apt install ./dist/tuxdoku_0.2.0_all.deb   # telepítés (függőségekkel együtt)
tuxdoku                                # vagy a menüből: Játékok → Tuxdoku
sudo apt remove tuxdoku                # eltávolítás
```

A karbantartó neve/e-mailje a `packaging/build_deb.sh` elején (`MAINTAINER=`) vagy a `TUXDOKU_MAINTAINER` környezeti változóval állítható. Kipróbálva: Ubuntu 24.04, Debian 12, Debian 13.

---

## English

A cheerful, pastel logic puzzle with penguins (Queens / one-star *Star Battle* rules), written in Python 3 with pygame 2 (pygame-ce works too).

> **Author:** Siposs Attila <sipiatti@gmail.com>  
> This game was created using *vibe coding*, with the help of **Grok Bot**.

**Rules:** the N×N grid is split into N coloured regions. Hide exactly N penguins so that every row, every column and every region holds exactly one penguin, and no two penguins touch – not even diagonally. Every puzzle has exactly one solution (verified by the built-in solver).

**Controls:** left click cycles empty → X → penguin → empty; right click toggles an X; dragging paints/erases many X marks; arrows + Space/Enter, X, P, Backspace, H (hint), **M (music on/off), S or N (sound effects on/off)**, Esc (menu), F11 (fullscreen).

**Sound:** cheerful effects (X mark, penguin placed, mistake, hint, level-complete fanfare, game over, subtle button hover/click) and two looping background tracks (menu and gameplay). Music and effects have separate volume sliders and mute toggles on the ⚙ settings screen (top-right of the menu, bottom-right icon row in game); settings are saved in `progress.json`. If no audio device is available (or `pygame.mixer` fails), the game runs silently; `--mute` skips opening the audio device entirely. All audio is synthesized by `tools/make_sounds.py` (CC0).

**Lives & hints:** 3 lives per level; placing a penguin on a cell that is not in the solution costs a life (X marks are free). Each life left at the end of a level adds one hint to the next level; the hint count is always clamped to `max_hints_allowed(N) = max(0, N − 2)` (see `tuxdoku/rules.py`). A hint reveals one correct penguin and auto-crosses the cells it rules out.

**Scoring** (`tuxdoku/rules.py: score_level`):

```
base         = 40 · N · (N − 3) · (1 + 0.1 · tier)      tier = 0,1,2 within a board size
par          = 4 s · N²
time_bonus   = base · max(0, par − t) / par
lives_bonus  = 25 · N · lives_left
hint_penalty = 30 · N · hints_used
score        = max(0, base + time_bonus + lives_bonus − hint_penalty)
```

**Debian package:** `packaging/build_deb.sh` builds a reproducible `dist/tuxdoku_<version>_all.deb` with plain `dpkg-deb` (no debhelper needed). Install with `sudo apt install ./dist/tuxdoku_0.2.0_all.deb`, remove with `sudo apt remove tuxdoku`. Depends: `python3 (>= 3.10)`, `python3-pygame (>= 2.1)`; tested on Ubuntu 24.04, Debian 12 (pygame 2.1.2) and Debian 13. Set the maintainer at the top of the script or via `TUXDOKU_MAINTAINER="Name <mail>"`. Files: game code in `/usr/share/tuxdoku`, launcher `/usr/games/tuxdoku` (+ `/usr/bin/tuxdoku` symlink), desktop entry, hicolor icons, man page `tuxdoku(6)`.

**Run:** `python3 -m tuxdoku` (needs `python3-pygame` or `pip install -r requirements.txt`), or `pip install .` and then `tuxdoku`. Tests: `python3 -m pytest`.

**Project layout**

```
tuxdoku/            game package (python3 -m tuxdoku)
  puzzle.py         rules, solver, generator (pure Python)
  rules.py          levels, hint cap, scoring
  game.py           level state (marks, lives, hints, timer)
  storage.py        progress / settings / high scores JSON
  audio.py          sound effects + music (silent fallback)
  app.py, ui.py, theme.py, resources.py   pygame front-end
  assets/           fonts (OFL), penguin + icon PNG/SVG, sounds/*.wav, music/*.ogg (CC0)
tools/make_assets.py   regenerates the artwork from SVG code
tools/make_sounds.py   synthesizes all sound effects + music (numpy, ffmpeg/libvorbis)
tools/screenshots.py   headless screenshots
data/                  desktop entry + hicolor/scalable icons
packaging/             build_deb.sh, launcher, man page, debian/ (control, changelog, copyright, maintainer scripts)
tests/              pytest suite
```

License: MIT (code); assets see [CREDITS.md](CREDITS.md).
