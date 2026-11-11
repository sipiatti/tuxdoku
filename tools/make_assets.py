#!/usr/bin/env python3
"""Generate Tuxdoku's original penguin and icon artwork (SVG sources + PNG renders).

All artwork produced by this script is original work for Tuxdoku and is
released under CC0 1.0 (public domain dedication). Re-run after editing:

    pip install cairosvg
    python3 tools/make_assets.py
"""
from pathlib import Path

import cairosvg

ROOT = Path(__file__).resolve().parent.parent / "tuxdoku" / "assets"
PNG_SIZE = 256

# (file id, body colour, body outline, accessory id, mood)
PENGUINS = [
    ("penguin", "#3b4060", "#262a40", "bowtie", "normal"),
    ("penguin_happy", "#3b4060", "#262a40", "bowtie", "happy"),
    ("penguin_sad", "#3b4060", "#262a40", "bowtie", "sad"),
]

# The game uses a single penguin "queen" (three moods); X markers are drawn in code.

ACCESSORIES = {
    "bowtie": """
      <g transform="translate(100 120)">
        <path d="M0 0 L-24 -13 Q-29 0 -24 13 Z" fill="#ff4d6d" stroke="#c9184a" stroke-width="3" stroke-linejoin="round"/>
        <path d="M0 0 L24 -13 Q29 0 24 13 Z" fill="#ff4d6d" stroke="#c9184a" stroke-width="3" stroke-linejoin="round"/>
        <circle r="7" fill="#ff758f" stroke="#c9184a" stroke-width="3"/>
      </g>""",
    "beanie": """
      <path d="M50 58 Q52 12 100 10 Q148 12 150 58 Z" fill="#4cc9f0" stroke="#277da1" stroke-width="4" stroke-linejoin="round"/>
      <path d="M62 30 Q100 18 138 30" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/>
      <rect x="44" y="50" width="112" height="20" rx="10" fill="#ffffff" stroke="#277da1" stroke-width="4"/>
      <circle cx="100" cy="10" r="13" fill="#ffffff" stroke="#277da1" stroke-width="4"/>""",
    "party": """
      <path d="M72 56 L100 -2 L128 56 Z" fill="#9b5de5" stroke="#5a189a" stroke-width="4" stroke-linejoin="round"/>
      <path d="M82 36 L118 36 M77 47 L123 47 M89 20 L111 20" stroke="#fee440" stroke-width="6" stroke-linecap="round"/>
      <circle cx="100" cy="0" r="10" fill="#00f5d4" stroke="#00a896" stroke-width="4"/>""",
    "headphones": """
      <path d="M44 86 Q44 20 100 20 Q156 20 156 86" fill="none" stroke="#ff4d8d" stroke-width="10" stroke-linecap="round"/>
      <rect x="28" y="72" width="26" height="40" rx="12" fill="#ff4d8d" stroke="#b5179e" stroke-width="4"/>
      <rect x="146" y="72" width="26" height="40" rx="12" fill="#ff4d8d" stroke="#b5179e" stroke-width="4"/>""",
    "sprout": """
      <path d="M100 48 Q98 30 100 18" fill="none" stroke="#2d6a4f" stroke-width="6" stroke-linecap="round"/>
      <path d="M100 26 Q74 2 58 20 Q76 38 100 26 Z" fill="#95d5b2" stroke="#2d6a4f" stroke-width="4" stroke-linejoin="round"/>
      <path d="M100 22 Q124 -4 144 12 Q126 34 100 22 Z" fill="#b7e4c7" stroke="#2d6a4f" stroke-width="4" stroke-linejoin="round"/>
      <circle cx="58" cy="122" r="0" fill="none"/>""",
    "crown": """
      <path d="M62 56 L58 14 L80 34 L100 6 L120 34 L142 14 L138 56 Z" fill="#ffd60a" stroke="#d39e00" stroke-width="4" stroke-linejoin="round"/>
      <circle cx="100" cy="40" r="7" fill="#ff4d6d" stroke="#c9184a" stroke-width="3"/>
      <circle cx="76" cy="44" r="5" fill="#4cc9f0" stroke="#277da1" stroke-width="3"/>
      <circle cx="124" cy="44" r="5" fill="#80ed99" stroke="#38a169" stroke-width="3"/>""",
    "wizard": """
      <path d="M48 60 Q100 44 152 60 Q160 66 150 70 Q100 58 50 70 Q40 66 48 60 Z" fill="#3a3f9e" stroke="#23266b" stroke-width="4" stroke-linejoin="round"/>
      <path d="M64 60 Q86 30 96 -2 Q110 16 136 58 Z" fill="#4a52c9" stroke="#23266b" stroke-width="4" stroke-linejoin="round"/>
      <path d="M100 22 l4 9 10 1 -8 6 3 10 -9 -6 -9 6 3 -10 -8 -6 10 -1 Z" fill="#ffd60a" stroke="#d39e00" stroke-width="2" stroke-linejoin="round"/>""",
    "bow": """
      <g transform="translate(128 40) rotate(18)">
        <path d="M0 0 Q-30 -26 -36 0 Q-30 26 0 0 Z" fill="#ffd23f" stroke="#e09f00" stroke-width="4" stroke-linejoin="round"/>
        <path d="M0 0 Q30 -26 36 0 Q30 26 0 0 Z" fill="#ffd23f" stroke="#e09f00" stroke-width="4" stroke-linejoin="round"/>
        <circle r="8" fill="#ffe66d" stroke="#e09f00" stroke-width="4"/>
      </g>""",
    "tophat": """
      <rect x="46" y="48" width="108" height="14" rx="7" fill="#2b2d42" stroke="#14151f" stroke-width="4"/>
      <rect x="66" y="0" width="68" height="54" rx="6" fill="#2b2d42" stroke="#14151f" stroke-width="4"/>
      <rect x="66" y="34" width="68" height="12" fill="#ff8fab"/>""",
}


def penguin_svg(body: str, outline: str, accessory: str, mood: str = "normal") -> str:
    acc = ACCESSORIES[accessory]
    # Accessories that sit *under* the head outline (headphones band) are drawn first.
    if mood == "happy":
        eyes = """  <path d="M74 86 Q84 72 94 86" fill="none" stroke="#1d1d2c" stroke-width="5" stroke-linecap="round"/>
  <path d="M106 86 Q116 72 126 86" fill="none" stroke="#1d1d2c" stroke-width="5" stroke-linecap="round"/>"""
    elif mood == "sad":
        eyes = """  <ellipse cx="84" cy="84" rx="8" ry="9" fill="#1d1d2c"/>
  <ellipse cx="116" cy="84" rx="8" ry="9" fill="#1d1d2c"/>
  <circle cx="86" cy="80" r="3" fill="#ffffff"/><circle cx="118" cy="80" r="3" fill="#ffffff"/>
  <path d="M72 70 L92 64 M128 70 L108 64" stroke="#1d1d2c" stroke-width="4" stroke-linecap="round"/>
  <path d="M124 94 Q130 104 124 108 Q118 104 124 94 Z" fill="#7cc6fe" stroke="#3a86ff" stroke-width="2"/>"""
    else:
        eyes = """  <ellipse cx="84" cy="82" rx="9" ry="11" fill="#1d1d2c"/>
  <ellipse cx="116" cy="82" rx="9" ry="11" fill="#1d1d2c"/>
  <circle cx="87" cy="77" r="3.6" fill="#ffffff"/>
  <circle cx="119" cy="77" r="3.6" fill="#ffffff"/>"""
    behind = acc if accessory == "headphones" else ""
    front = "" if accessory == "headphones" else acc
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -8 200 212" width="{PNG_SIZE}" height="{PNG_SIZE}">
  <ellipse cx="100" cy="196" rx="62" ry="7" fill="#000000" opacity="0.12"/>
  {behind}
  <!-- feet -->
  <ellipse cx="72" cy="186" rx="24" ry="10" fill="#ffa62b" stroke="#e07b00" stroke-width="4"/>
  <ellipse cx="128" cy="186" rx="24" ry="10" fill="#ffa62b" stroke="#e07b00" stroke-width="4"/>
  <!-- wings -->
  <ellipse cx="42" cy="128" rx="16" ry="38" transform="rotate(18 42 128)" fill="{body}" stroke="{outline}" stroke-width="4"/>
  <ellipse cx="158" cy="128" rx="16" ry="38" transform="rotate(-18 158 128)" fill="{body}" stroke="{outline}" stroke-width="4"/>
  <!-- body -->
  <path d="M100 40 C146 40 162 84 162 124 C162 166 136 184 100 184 C64 184 38 166 38 124 C38 84 54 40 100 40 Z"
        fill="{body}" stroke="{outline}" stroke-width="4"/>
  <!-- belly + face -->
  <path d="M100 92 C130 92 142 116 142 140 C142 164 124 176 100 176 C76 176 58 164 58 140 C58 116 70 92 100 92 Z" fill="#fffdf7"/>
  <ellipse cx="82" cy="82" rx="21" ry="24" fill="#fffdf7"/>
  <ellipse cx="118" cy="82" rx="21" ry="24" fill="#fffdf7"/>
{eyes}
  <!-- cheeks -->
  <ellipse cx="68" cy="102" rx="9" ry="6" fill="#ff8fab" opacity="0.65"/>
  <ellipse cx="132" cy="102" rx="9" ry="6" fill="#ff8fab" opacity="0.65"/>
  <!-- beak -->
  <path d="M86 98 Q100 90 114 98 Q108 112 100 113 Q92 112 86 98 Z" fill="#ffb627" stroke="#e07b00" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M90 102 Q100 106 110 102" fill="none" stroke="#e07b00" stroke-width="2.5" stroke-linecap="round"/>
  {front}
</svg>"""


ICONS = {
    "heart": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="128" height="128">
  <path d="M50 88 C20 66 6 50 6 32 C6 18 17 8 30 8 C40 8 46 14 50 22 C54 14 60 8 70 8 C83 8 94 18 94 32 C94 50 80 66 50 88 Z"
        fill="#ff5d8f" stroke="#c9184a" stroke-width="5" stroke-linejoin="round"/>
  <path d="M24 26 Q28 18 36 18" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round" opacity="0.8"/>
</svg>""",
    "heart_empty": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="128" height="128">
  <path d="M50 88 C20 66 6 50 6 32 C6 18 17 8 30 8 C40 8 46 14 50 22 C54 14 60 8 70 8 C83 8 94 18 94 32 C94 50 80 66 50 88 Z"
        fill="#ece4f2" stroke="#b9a9c9" stroke-width="5" stroke-linejoin="round" stroke-dasharray="1 0"/>
  <path d="M50 22 L42 40 L56 52 L46 70" fill="none" stroke="#b9a9c9" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "bulb": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="128" height="128">
  <path d="M50 8 C30 8 18 22 18 40 C18 54 28 60 34 70 L66 70 C72 60 82 54 82 40 C82 22 70 8 50 8 Z" fill="#ffe66d" stroke="#e09f00" stroke-width="5" stroke-linejoin="round"/>
  <rect x="34" y="72" width="32" height="10" rx="4" fill="#a0a8c0" stroke="#6c7490" stroke-width="4"/>
  <rect x="38" y="84" width="24" height="9" rx="4" fill="#a0a8c0" stroke="#6c7490" stroke-width="4"/>
  <path d="M34 34 Q36 22 48 20" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round"/>
</svg>""",
    "eraser": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="128" height="128">
  <g transform="rotate(-35 50 50)">
    <rect x="14" y="34" width="72" height="34" rx="8" fill="#9bf6ff" stroke="#1b98a8" stroke-width="5"/>
    <rect x="14" y="34" width="30" height="34" rx="8" fill="#ffadad" stroke="#d9485f" stroke-width="5"/>
  </g>
  <path d="M20 90 L84 90" stroke="#b9a9c9" stroke-width="5" stroke-linecap="round"/>
</svg>""",
    "music": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="128" height="128">
  <path d="M38 22 L82 12 L82 66" fill="none" stroke="#ffffff" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="M38 22 L38 74" stroke="#ffffff" stroke-width="9" stroke-linecap="round"/>
  <path d="M38 30 L82 20" stroke="#ffffff" stroke-width="12"/>
  <ellipse cx="27" cy="76" rx="15" ry="11" transform="rotate(-20 27 76)" fill="#ffffff"/>
  <ellipse cx="71" cy="68" rx="15" ry="11" transform="rotate(-20 71 68)" fill="#ffffff"/>
</svg>""",
    "music_off": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="128" height="128">
  <g opacity="0.75">
  <path d="M38 22 L82 12 L82 66" fill="none" stroke="#ffffff" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="M38 22 L38 74" stroke="#ffffff" stroke-width="9" stroke-linecap="round"/>
  <path d="M38 30 L82 20" stroke="#ffffff" stroke-width="12"/>
  <ellipse cx="27" cy="76" rx="15" ry="11" transform="rotate(-20 27 76)" fill="#ffffff"/>
  <ellipse cx="71" cy="68" rx="15" ry="11" transform="rotate(-20 71 68)" fill="#ffffff"/>
  </g>
  <path d="M12 12 L88 88" stroke="#ff4d6d" stroke-width="12" stroke-linecap="round"/>
</svg>""",
    "speaker": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="128" height="128">
  <path d="M10 38 L28 38 L50 18 L50 82 L28 62 L10 62 Z" fill="#ffffff" stroke="#ffffff" stroke-width="6" stroke-linejoin="round"/>
  <path d="M62 36 Q72 50 62 64" fill="none" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>
  <path d="M72 24 Q92 50 72 76" fill="none" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>
</svg>""",
    "speaker_off": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="128" height="128">
  <path d="M10 38 L28 38 L50 18 L50 82 L28 62 L10 62 Z" fill="#ffffff" stroke="#ffffff" stroke-width="6" stroke-linejoin="round" opacity="0.75"/>
  <path d="M64 36 L88 64 M88 36 L64 64" stroke="#ff4d6d" stroke-width="10" stroke-linecap="round"/>
</svg>""",
    "gear": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="128" height="128">
  <g fill="#ffffff">
    <circle cx="50" cy="50" r="28"/>
    <g id="t"><rect x="42" y="6" width="16" height="22" rx="4"/></g>
    <use href="#t" transform="rotate(45 50 50)"/><use href="#t" transform="rotate(90 50 50)"/>
    <use href="#t" transform="rotate(135 50 50)"/><use href="#t" transform="rotate(180 50 50)"/>
    <use href="#t" transform="rotate(225 50 50)"/><use href="#t" transform="rotate(270 50 50)"/>
    <use href="#t" transform="rotate(315 50 50)"/>
  </g>
  <circle cx="50" cy="50" r="11" fill="#b291ff"/>
</svg>""",
    "question": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="128" height="128">
  <path d="M30 34 Q30 12 50 12 Q72 12 72 32 Q72 46 56 52 Q50 55 50 64" fill="none" stroke="#ffffff" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="50" cy="84" r="8" fill="#ffffff"/>
</svg>""",
    "star": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="128" height="128">
  <path d="M50 6 L62 36 L94 38 L69 58 L78 90 L50 72 L22 90 L31 58 L6 38 L38 36 Z" fill="#ffd60a" stroke="#e09f00" stroke-width="5" stroke-linejoin="round"/>
  <path d="M40 40 L46 30" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
</svg>""",
    "snowflake": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="64" height="64">
  <g stroke="#ffffff" stroke-width="7" stroke-linecap="round" fill="none">
    <path d="M50 8 L50 92 M14 29 L86 71 M14 71 L86 29"/>
    <path d="M40 16 L50 26 L60 16 M40 84 L50 74 L60 84"/>
  </g>
</svg>""",
}


def main() -> None:
    (ROOT / "penguins").mkdir(parents=True, exist_ok=True)
    (ROOT / "icons").mkdir(parents=True, exist_ok=True)
    (ROOT / "svg").mkdir(parents=True, exist_ok=True)
    for pid, body, outline, acc, mood in PENGUINS:
        svg = penguin_svg(body, outline, acc, mood)
        (ROOT / "svg" / f"{pid}.svg").write_text(svg, encoding="utf-8")
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(ROOT / "penguins" / f"{pid}.png"),
                         output_width=PNG_SIZE, output_height=PNG_SIZE)
    for name, svg in ICONS.items():
        (ROOT / "svg" / f"{name}.svg").write_text(svg, encoding="utf-8")
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(ROOT / "icons" / f"{name}.png"))
    # app icon = classic penguin
    cairosvg.svg2png(bytestring=penguin_svg(*PENGUINS[0][1:]).encode(),
                     write_to=str(ROOT / "icons" / "tuxdoku.png"), output_width=128, output_height=128)
    # desktop icons for packaging (hicolor theme sizes + scalable SVG)
    data = ROOT.parent.parent / "data" / "icons"
    app_svg = penguin_svg(*PENGUINS[1][1:])          # happy penguin
    (data).mkdir(parents=True, exist_ok=True)
    (data / "tuxdoku.svg").write_text(app_svg, encoding="utf-8")
    for size in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        out = data / "hicolor" / f"{size}x{size}" / "apps"
        out.mkdir(parents=True, exist_ok=True)
        cairosvg.svg2png(bytestring=app_svg.encode(), write_to=str(out / "tuxdoku.png"),
                         output_width=size, output_height=size)
    print("assets written to", ROOT)


if __name__ == "__main__":
    main()
