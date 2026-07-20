#!/usr/bin/env python3
"""Generate scenicArt.ts — a playful Hokusai PIXEL-ART scene as half-block cells.

v2: the photo downsample read as blur at 18px height (operator verdict). This
paints the scene procedurally at native grid resolution — flat woodblock
colors, crisp edges, designed FOR the cell grid: cream sky, persimmon sun,
snow-capped Fuji, the great curling wave with foam fingers, a small boat.
Rendered by ScenicStrip as U+2580 cells (fg=top px, bg=bottom px) — one
universally-covered glyph, truecolor paint, alignment guaranteed by math.

Usage:
  python3 scripts/scenic_generate.py > src/components/scenicArt.ts
  python3 scripts/scenic_generate.py --preview     # letter-map shape check
"""

import json
import math
import sys

H = 18  # pixel rows -> 9 terminal rows
WIDTHS = (118, 98, 78)

NIGHT = (0x10, 0x14, 0x1C)   # theme canvas
CREAM = (0xDC, 0xD7, 0xBA)   # foam/cream sky (theme foam)
CREAM2 = (0xC8, 0xC0, 0x93)  # lower warm sky (theme mist)
DEEP = (0x1B, 0x33, 0x52)    # prussian deep water
MID = (0x2D, 0x4F, 0x67)     # theme river
LIGHT = (0x7E, 0x9C, 0xD8)   # theme wave (inner crest light)
FOAM = (0xF2, 0xEE, 0xDC)    # wave foam
SLATE = (0x4A, 0x5B, 0x78)   # fuji body
SNOW = (0xEE, 0xF2, 0xF6)
SUN = (0xFF, 0x9E, 0x3B)     # theme persimmon
SUNCORE = (0xFF, 0xC4, 0x85)
HULL = (0x2A, 0x22, 0x1A)    # boat silhouette

PREVIEW_CHARS = {
    NIGHT: " ", CREAM: ".", CREAM2: ",", DEEP: "b", MID: "m", LIGHT: "L",
    FOAM: "W", SLATE: "F", SNOW: "S", SUN: "O", SUNCORE: "o", HULL: "#",
}


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def paint(w):
    px = [[CREAM for _ in range(w)] for _ in range(H)]

    # Sky: warm band low, cream high — flat woodblock fields.
    for y in range(H):
        for x in range(w):
            px[y][x] = CREAM if y < 7 else CREAM2 if y < 10 else MID

    # Sun disk, upper right air.
    sun_cx, sun_cy, sun_r = w * 0.80, 3.4, 2.4
    for y in range(H):
        for x in range(w):
            d = math.hypot((x - sun_cx) * 0.55, y - sun_cy)
            if d < sun_r * 0.55:
                px[y][x] = SUNCORE
            elif d < sun_r:
                px[y][x] = SUN

    # Fuji: triangle with jagged snow cap, sitting on the horizon.
    fuji_cx, fuji_peak_y, fuji_base_y, fuji_half = w * 0.66, 4, 12, w * 0.085
    for y in range(fuji_peak_y, fuji_base_y):
        spread = fuji_half * (y - fuji_peak_y + 1) / (fuji_base_y - fuji_peak_y)
        for x in range(int(fuji_cx - spread), int(fuji_cx + spread) + 1):
            if 0 <= x < w:
                snow_line = fuji_peak_y + 3 + ((x + y) % 2)
                px[y][x] = SNOW if y <= snow_line else SLATE

    # Water body.
    for y in range(12, H):
        for x in range(w):
            px[y][x] = DEEP if y >= 14 else MID
    # Wave streaks — rhythmic woodblock lines.
    for y in (13, 15, 16):
        for x in range(w):
            if (x // 5 + y) % 2 == 0:
                px[y][x] = lerp(DEEP, LIGHT, 0.35 if y > 13 else 0.5)

    # THE WAVE: swell on the left, crest curling right with foam fingers.
    crest_x = w * 0.17
    for x in range(int(w * 0.55)):
        t = (x - crest_x) / (w * 0.16)
        top = 3 + 9 * (1 - math.exp(-t * t)) if x > crest_x else 3 + 1.2 * ((crest_x - x) / crest_x) ** 1.5 * 9
        top = max(2, min(12, top))
        for y in range(int(top), 12):
            depth = (y - top) / max(12 - top, 1)
            px[y][x] = DEEP if depth > 0.55 else MID if depth > 0.22 else LIGHT
        # Foam edge along the crest line (thick only on the back of the swell).
        edge = int(top)
        if 0 <= edge < H:
            px[edge][x] = FOAM
            if edge + 1 < H and x < crest_x:
                px[edge + 1][x] = FOAM

    # Curl lip: a clean foam hook reaching right from the peak over the
    # falling face, with spaced fingers dangling — air stays clear beneath.
    lip_y = 2
    lip_start, lip_end = int(crest_x), int(crest_x + w * 0.12)
    for x in range(lip_start, lip_end):
        px[lip_y][x] = FOAM
        px[lip_y + 1][x] = FOAM
    for i, fx in enumerate(range(lip_start + 3, lip_end + 5, 4)):
        drop = 2 + (i % 2)
        for dy in range(drop):
            y = lip_y + 2 + dy
            if 0 <= fx < w and y < 10:
                px[y][fx] = FOAM if dy < drop - 1 else lerp(FOAM, LIGHT, 0.5)

    # Secondary swell mid-field.
    s_cx = w * 0.46
    for x in range(int(w * 0.36), int(w * 0.58)):
        t = (x - s_cx) / (w * 0.07)
        top = 9 + 2.4 * (t * t) if abs(t) < 1.4 else 12
        top = min(12, top)
        for y in range(int(top), 12):
            px[y][x] = MID if y > top + 1 else LIGHT
        if int(top) < 12:
            px[int(top)][x] = FOAM

    # A small boat on the open sea right of Fuji — the playful bit.
    boat_x, boat_y = int(w * 0.86), 12
    for dx in range(5):
        if 0 <= boat_x + dx < w:
            px[boat_y][boat_x + dx] = HULL
    for dx in (1, 3):
        if 0 <= boat_x + dx < w:
            px[boat_y - 1][boat_x + dx] = HULL

    # Edge + top fade into the night canvas so the band sits IN the theme.
    fade_cols, fade_rows = 9, 2
    for y in range(H):
        for x in range(w):
            t = 0.0
            if x < fade_cols:
                t = max(t, 1 - x / fade_cols)
            if x >= w - fade_cols:
                t = max(t, 1 - (w - 1 - x) / fade_cols)
            if y < fade_rows:
                t = max(t, (1 - y / fade_rows) * 0.8)
            if t > 0:
                px[y][x] = lerp(px[y][x], NIGHT, min(t, 1.0))
    return px


def preview(px):
    def char(c):
        if c in PREVIEW_CHARS:
            return PREVIEW_CHARS[c]
        return "+"
    for row in px:
        print("".join(char(c) for c in row))


def hexc(c):
    return "#{:02x}{:02x}{:02x}".format(*c)


def to_rows(px, w):
    rows = []
    for r in range(H // 2):
        segments = []
        run = None
        for x in range(w):
            fg, bg = hexc(px[r * 2][x]), hexc(px[r * 2 + 1][x])
            if run and run["fg"] == fg and run["bg"] == bg:
                run["n"] += 1
            else:
                run = {"fg": fg, "bg": bg, "n": 1}
                segments.append(run)
        rows.append(segments)
    return rows


def main():
    if "--preview" in sys.argv:
        preview(paint(118))
        return
    variants = {str(w): to_rows(paint(w), w) for w in WIDTHS}
    print("// GENERATED by scripts/scenic_generate.py — do not hand-edit.")
    print("// Playful Hokusai pixel-art scene (sun, Fuji, curling wave, boat)")
    print("// as half-block truecolor cells. Data, not styling: theme law exempt.")
    print("export type ScenicSegment = {fg: string; bg: string; n: number};")
    print("export const SCENIC_ROWS = %d;" % (H // 2))
    print(
        "export const SCENIC_VARIANTS: Record<string, ScenicSegment[][]> = "
        + json.dumps(variants, separators=(",", ":"))
        + ";"
    )
    print("export const SCENIC_WIDTHS = %s;" % list(WIDTHS))


if __name__ == "__main__":
    main()
