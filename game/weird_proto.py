#!/usr/bin/env python3
"""Weird-style previews: out/w_tiles.png, out/w_world.png, out/w_zone_*.png, out/w_cycle.gif"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import proto, weird
from weird import F, TS as T, Painter8, Species

OUT = proto.OUT


def world8(wd, sp):
    p = Painter8(proto.W, proto.H)
    ys, xs = np.mgrid[0:proto.H, 0:proto.W]
    R = proto.rnd_cells(xs, ys, wd.seed)
    for y in range(proto.H):
        for x in range(proto.W):
            weird.paint(p, sp, x, y, wd.biome[y, x], R[y, x], local=False)
    def ln(a, b, idx, w):
        x0, y0, x1, y1 = a[0] * T + 8, a[1] * T + 8, b[0] * T + 8, b[1] * T + 8
        for i in range(T + 1):
            cx, cy = int(x0 + (x1 - x0) * i / T), int(y0 + (y1 - y0) * i / T)
            p.img[max(0, cy - w // 2):cy + w - w // 2, max(0, cx - w // 2):cx + w - w // 2] = idx
    for a, b in wd.rlinks:
        ln(a, b, F("sea", 3), 4)
    for a, b in wd.rlinks:
        ln(a, b, F("sea", 6), 1)
    for a, b in wd.dlinks:
        ln(a, b, F("brick", 5), 2)
    for (x, y) in wd.towns:
        p.fill(x, y, 0); p.sprite(x, y, sp.get("house", "hut", 0), {"1": F("brick", 6), "2": F("brick", 3), "3": F("eye", 7)})
    return p.img


def zone8(wd, sp, ox, oy, zw, zh):
    b, X, Y = proto.gen_cells(wd, ox, oy, zw, zh)
    p = Painter8(zw, zh)
    gx, gy = np.floor(X * proto.ZS).astype(np.int64), np.floor(Y * proto.ZS).astype(np.int64)
    R = proto.rnd_cells(gx, gy, wd.seed + 99)
    for y in range(zh):
        for x in range(zw):
            weird.paint(p, sp, x, y, b[y, x], R[y, x])
    return p.img, b


def save8(img8, name, t=0.0, scale=2):
    im = Image.fromarray(weird.to_rgb(img8, t))
    im.resize((im.width * scale, im.height * scale), Image.NEAREST).save(os.path.join(OUT, name))


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1337
    wd = proto.World(seed)
    sp = Species(seed)
    save8(world8(wd, sp), "w_world.png", scale=1)
    # tile sheet: 4x3 block of each biome
    names = ["deep", "ocean", "shallow", "river", "seaice", "icesheet", "drift", "tundra", "taiga", "grass", "meadow",
             "savanna", "forest", "jungle", "swamp", "desert", "salt", "badlands", "hills", "mountain", "peak", "ash",
             "lava", "crust", "volcano", "fungal", "crystal", "beach", "road", "plaza", "house", "bridge"]
    cols, bw, bh = 6, 4, 3
    p = Painter8(cols * (bw + 1), math.ceil(len(names) / cols) * (bh + 1))
    for n, nm in enumerate(names):
        ox, oy = (n % cols) * (bw + 1), (n // cols) * (bh + 1)
        for yy in range(bh):
            for xx in range(bw):
                r = proto.rnd_cells(np.array(ox + xx + n * 31), np.array(oy + yy), 7)
                b = nm
                if nm in ("volcano", "house") and (xx, yy) != (1, 1):
                    b = {"volcano": "ash", "house": "plaza"}[nm]
                if nm == "bridge" and yy != 1:
                    b = "river"
                weird.paint(p, sp, ox + xx, oy + yy, b, r, local=nm not in ("volcano", "house") and not (nm in ("forest", "jungle", "fungal", "crystal", "taiga") and r[5] < 0.5))
    im = Image.fromarray(weird.to_rgb(p.img)).resize((p.img.shape[1] * 2, p.img.shape[0] * 2), Image.NEAREST)
    d = ImageDraw.Draw(im)
    fnt = ImageFont.truetype("/usr/share/fonts/noto/NotoSans-Bold.ttf", 18)
    for n, nm in enumerate(names):
        ox, oy = (n % cols) * (bw + 1), (n // cols) * (bh + 1)
        d.text((ox * T * 2 + 2, (oy + bh) * T * 2 + 3), nm, fill=(200, 200, 200), font=fnt)
    im.save(os.path.join(OUT, "w_tiles.png"))
    # zones
    rng = np.random.default_rng(seed)
    zones = {"town": wd.towns[0] if wd.towns else (50, 30)}
    for nm, bs in {"forest": ["forest"], "jungle": ["jungle", "swamp"], "fungal": ["fungal"], "crystal": ["crystal"],
                   "frozen": ["taiga", "seaice"], "volcano": ["volcano"], "desert": ["desert", "badlands"]}.items():
        q = proto.find(wd, bs, rng)
        if q:
            zones[nm] = q
    zw, zh = 48, 30
    imgs = {}
    for nm, (x, y) in zones.items():
        img, _ = zone8(wd, sp, x + 0.5 - zw / 24, y + 0.5 - zh / 24, zw, zh)
        imgs[nm] = img
        save8(img, f"w_zone_{nm}.png")
    # palette cycling demo
    base = imgs.get("crystal", imgs["town"])
    frames = [Image.fromarray(weird.to_rgb(base, k * 0.25)) for k in range(24)]
    frames[0].save(os.path.join(OUT, "w_cycle.gif"), save_all=True, append_images=frames[1:], duration=90, loop=0)
    print("zones", list(zones))


if __name__ == "__main__":
    main()
