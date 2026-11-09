"""Abandoned places dotted round the world: 33 layouts (walls, floors, props), placed by the seed.

Each zone has a ~1 in 4 chance of a structure suited to its land. Layouts are little ASCII plans;
they're turned and mirrored at random. Shared map chars:
  #  concrete wall   w  wooden wall   %  broken wall   .  concrete floor   ,  floorboards
  _  packed earth    *  scorched ground   +  doorway (floor)   =  railway   f  fence
anything else is a prop from the layout's own legend (see PROPS for the sprite of each).
"""
import math, zlib
import numpy as np
import weird
from weird import canvas, put, line, disc, F

# ── prop sprites (design grid 16x16; big ones drawn at higher res) ──


def p_mast(r):
    c = canvas()
    for y in np.arange(1, 16, 0.25):
        w = 0.8 + (y - 1) / 15 * 2.6
        put(c, 7.5 - w, y, "2"); put(c, 7.5 + w, y, "2")
    for k in range(7):
        y0 = 1.5 + k * 2; y1 = y0 + 2
        w0 = 0.8 + (y0 - 1) / 15 * 2.6; w1 = 0.8 + (y1 - 1) / 15 * 2.6
        line(c, 7.5 - w0, y0, 7.5 + w1, y1, "1"); line(c, 7.5 + w0, y0, 7.5 - w1, y1, "1")
    line(c, 1, 2, 14, 2, "1"); line(c, 2.5, 4, 12.5, 4, "1")
    for x in (1, 4, 11, 14):
        line(c, x, 0.5, x, 3.2, "3")
    return c


def p_dish(r):
    c = canvas()
    line(c, 7.5, 15, 7.5, 10, "2"); line(c, 5, 15, 10, 15, "2"); line(c, 6, 15, 7.5, 11, "2"); line(c, 9, 15, 7.5, 11, "2")
    for a in np.linspace(-1.3, 1.3, 90):
        for rr in np.arange(0, 6.5, 0.25):
            x, y = 7.5 + math.sin(a) * rr, 7 - math.cos(a) * rr * 0.45 + rr * 0.35
            put(c, x, y, "1" if rr < 6.2 else "3")
    line(c, 7.5, 7, 7.5, 3, "2"); disc(c, 7.5, 3, 0.7, "3")
    return c


def p_dome(r):
    c = canvas()
    for y in np.arange(2, 15, 0.25):
        for x in np.arange(1, 15, 0.25):
            d = (x - 7.5) ** 2 + ((y - 9) * 1.05) ** 2
            if d < 6.5 ** 2 and y < 13:
                put(c, x, y, "2" if x + (y - 9) * 0.6 > 9.5 else "1")
    for yy in (5, 7.5, 10):
        for x in np.arange(1.5, 13.5, 0.25):
            if (x - 7.5) ** 2 + ((yy - 9) * 1.05) ** 2 < 6.3 ** 2:
                put(c, x, yy, "3")
    for x in np.arange(2, 13.01, 0.25):
        put(c, x, 13, "2"); put(c, x, 14, "2"); put(c, x, 15, "2")
    return c


def p_tower(r):
    c = canvas()
    for lx, rx in ((3, 5), (12, 10)):
        line(c, lx, 15, rx, 7, "2")
    line(c, 4, 12, 11, 12, "1"); line(c, 4.5, 10, 10.5, 10, "1"); line(c, 4, 12, 10.5, 10, "1")
    for x in np.arange(3.5, 12, 0.25):
        for y in np.arange(5, 7.01, 0.25):
            put(c, x, y, "1")
    for x in np.arange(3, 12.5, 0.25):
        put(c, x, 4.5, "2")
    for k in np.arange(0, 3, 0.25):
        line(c, 2.5 + k, 4.5 - k, 12.5 - k, 4.5 - k, "3")
    return c


def p_watertower(r):
    c = canvas()
    for lx, rx in ((4, 6), (11, 9)):
        line(c, lx, 15, rx, 8, "2")
    line(c, 5, 12, 10, 12, "2")
    for y in np.arange(2, 8.01, 0.25):
        for x in np.arange(3.5, 11.6, 0.25):
            put(c, x, y, "2" if x > 9.5 else "1")
    for x in np.arange(3.5, 11.6, 0.25):
        put(c, x, 2, "3"); put(c, x, 5, "3")
    return c


def p_turbine(r):
    c = canvas()
    line(c, 7.5, 15, 7.5, 4, "1"); line(c, 8, 15, 8, 4, "2")
    a0 = r.uniform(0, 6.28)
    for k in range(3):
        a = a0 + k * 2.094
        line(c, 7.7, 4, 7.7 + math.cos(a) * 6.5, 4 + math.sin(a) * 6.5, "3")
    disc(c, 7.7, 4, 0.8, "2")
    return c


def p_radio(r):
    c = canvas()
    line(c, 7.5, 15, 7.5, 0.5, "1")
    for k in np.arange(1, 15, 1.2):
        line(c, 7, k, 8, k + 0.6, "2")
    for x in (1, 14):
        line(c, 7.5, 3, x, 15, "2"); line(c, 7.5, 8, x, 15, "2")
    disc(c, 7.5, 0.7, 0.6, "3")
    return c


def p_logs(r):
    c = canvas()
    rows = [(13.5, [3, 6, 9, 12]), (11, [4.5, 7.5, 10.5]), (8.5, [6, 9])]
    for y, xs in rows:
        for x in xs:
            disc(c, x, y, 1.5, "1"); disc(c, x, y, 0.6, "3")
    line(c, 1.5, 15, 13.5, 15, "2")
    return c


def p_stump(r):
    c = canvas()
    for y in np.arange(11, 15, 0.25):
        line(c, 5, y, 10, y, "2")
    disc(c, 7.5, 11, 2.6, "1"); disc(c, 7.5, 11, 1.4, "3"); disc(c, 7.5, 11, 0.5, "1")
    line(c, 9, 10, 12, 6, "2")                        # an axe left in it
    return c


def p_tent(r):
    c = canvas()
    for y in np.arange(4, 15.01, 0.25):
        w = (y - 4) / 11 * 6.5
        for x in np.arange(7.5 - w, 7.5 + w + 0.01, 0.25):
            put(c, x, y, "2" if x > 7.5 + w * 0.2 else "1")
    line(c, 7.5, 9, 7.5, 15, "3"); line(c, 7.5, 3, 7.5, 4.5, "3")
    return c


def p_rack(r):
    c = canvas()
    line(c, 3, 15, 3, 6, "2"); line(c, 12, 15, 12, 6, "2"); line(c, 2, 6, 13, 6, "2")
    for x in (5, 7.5, 10):
        for y in np.arange(6, 11, 0.25):
            line(c, x - 1, y, x + 1, y, "1")
    return c


def p_crate(r):
    c = canvas()
    for y in np.arange(8, 15.01, 0.25):
        line(c, 4, y, 11, y, "1")
    for x in (4, 11):
        line(c, x, 8, x, 15, "2")
    line(c, 4, 8, 11, 8, "3"); line(c, 4, 15, 11, 15, "2"); line(c, 4, 8, 11, 15, "2"); line(c, 11, 8, 4, 15, "2")
    return c


def p_barrel(r):
    c = canvas()
    for y in np.arange(8, 15.01, 0.25):
        line(c, 5.5, y, 9.5, y, "1")
    for y in (9, 12, 14.5):
        line(c, 5.5, y, 9.5, y, "2")
    line(c, 5.5, 8, 9.5, 8, "3")
    return c


def p_wagon(r):
    c = canvas()
    for y in np.arange(4, 10, 0.25):                    # canvas cover
        w = 5.5 - abs(y - 7) * 0.3
        line(c, 7.5 - w, y, 7.5 + w, y, "1")
    for y in np.arange(10, 12.01, 0.25):
        line(c, 1.5, y, 13.5, y, "2")
    disc(c, 3.5, 13.5, 1.6, "2"); disc(c, 11.5, 13.5, 1.6, "2"); disc(c, 3.5, 13.5, 0.5, "3"); disc(c, 11.5, 13.5, 0.5, "3")
    return c


def p_hull(r):
    c = canvas()
    for y in np.arange(5, 15, 0.25):
        w = 6.5 - abs(y - 10) * 0.4 + r.uniform(-0.5, 0.5)
        for x in np.arange(7.5 - w, 7.5 + w, 0.25):
            if r.random() > 0.04:
                put(c, x, y, "1" if y < 10 else "2")
    for x in np.arange(2.5, 12.5, 2):
        disc(c, x, 8, 0.6, "3")
    for k in range(5):
        line(c, 1.5 + k * 3, 5, 1.5 + k * 3, 14.5, "2")
    return c


def p_debris(r):
    c = canvas()
    for _ in range(r.integers(3, 6)):
        x, y = r.uniform(2, 13), r.uniform(10, 15)
        line(c, x, y, x + r.uniform(-2, 2), y + r.uniform(-1, 1), "1" if r.random() < 0.6 else "2")
    return c


def p_drill(r):
    c = canvas()
    line(c, 3, 15, 7.5, 1, "2"); line(c, 12, 15, 7.5, 1, "2")
    for y in np.arange(3, 15, 2):
        w = (y - 1) / 14 * 4.5
        line(c, 7.5 - w, y, 7.5 + w, y + 2, "1")
    line(c, 7.5, 1, 7.5, 15, "3")
    for y in np.arange(13, 15.01, 0.25):
        line(c, 4, y, 11, y, "2")
    return c


def p_cart(r):
    c = canvas()
    for y in np.arange(9, 13, 0.25):
        w = 4 - (y - 9) * 0.3
        line(c, 7.5 - w, y, 7.5 + w, y, "1")
    disc(c, 9, 8.5, 1.4, "3"); disc(c, 6.5, 8.8, 1.2, "3")
    disc(c, 5, 14, 1.1, "2"); disc(c, 10, 14, 1.1, "2")
    return c


def p_pump(r):
    c = canvas()
    for y in np.arange(5, 15.01, 0.25):
        line(c, 5, y, 10, y, "1")
    for y in np.arange(6, 8.01, 0.25):
        line(c, 6, y, 9, y, "3")
    line(c, 10, 9, 12, 9, "2"); line(c, 12, 9, 12, 13, "2")
    return c


def p_post(r):
    c = canvas()
    for x in np.arange(6.5, 8.6, 0.25):
        line(c, x, 2, x, 15, "1")
    line(c, 6.5, 2, 8.5, 2, "3")
    return c


def p_car(r):
    c = canvas()
    for y in np.arange(7, 10, 0.25):
        line(c, 4.5 + (10 - y) * 0.4, y, 10.5 - (10 - y) * 0.3, y, "2")
    for y in np.arange(10, 13.5, 0.25):
        line(c, 1.5, y, 14, y, "1")
    line(c, 5.5, 8, 7.5, 8, "3"); line(c, 8.5, 8, 9.8, 8, "3")
    disc(c, 4, 13.6, 1.4, "2"); disc(c, 11.5, 13.6, 1.4, "2")
    for _ in range(4):
        put(c, r.uniform(2, 13), r.uniform(10, 13), "2")
    return c


def p_truck(r):
    c = canvas()
    for y in np.arange(4, 12, 0.25):
        line(c, 1, y, 10, y, "1")
    for y in np.arange(7, 12, 0.25):
        line(c, 10.5, y, 14.5, y, "2")
    line(c, 11.5, 8, 13.5, 8, "3")
    for x in (3, 7, 12.5):
        disc(c, x, 13, 1.4, "2")
    return c


def p_carriage(r):
    c = canvas()
    for y in np.arange(5, 12.5, 0.25):
        line(c, 0.5, y, 15.5, y, "1")
    for x in np.arange(2, 14.5, 3):
        for y in np.arange(6.5, 8.5, 0.25):
            line(c, x, y, x + 1.6, y, "3")
    line(c, 0.5, 12.5, 15.5, 12.5, "2")
    for x in (2.5, 5, 11, 13.5):
        disc(c, x, 13.6, 1.0, "2")
    return c


def p_barrier(r):
    c = canvas()
    line(c, 2, 15, 2, 9, "2"); line(c, 13, 15, 13, 9, "2")
    for x in np.arange(1, 14.5, 0.25):
        for y in np.arange(9, 11, 0.25):
            put(c, x, y, "3" if int(x / 2) % 2 else "1")
    return c


def p_sandbag(r):
    c = canvas()
    for row, y in enumerate((14, 12.3, 10.6)):
        for x in np.arange(2 + row, 14 - row, 2.6):
            disc(c, x, y, 1.3, "1"); put(c, x + 0.8, y + 0.8, "2")
    return c


def p_grave(r):
    c = canvas()
    for y in np.arange(7, 14, 0.25):
        line(c, 5.5, y, 9.5, y, "1")
    disc(c, 7.5, 7, 2, "1")
    line(c, 6.5, 8.5, 8.5, 8.5, "2"); line(c, 7.5, 7.5, 7.5, 10.5, "2")
    for y in np.arange(14, 15.5, 0.25):
        line(c, 4, y, 11, y, "2")
    return c


def p_stone(r):
    c = canvas()
    h, w = r.uniform(9, 13), r.uniform(1.8, 2.8)
    for y in np.arange(15 - h, 15.01, 0.25):
        ww = w * (0.8 + 0.2 * math.sin(y * 2.1)) * (1 - (15 - y) / h * 0.15)
        for x in np.arange(7.5 - ww, 7.5 + ww, 0.25):
            put(c, x, y, "2" if x > 7.5 + ww * 0.3 else "1")
    for _ in range(4):
        put(c, 7.5 + r.uniform(-w, w) * 0.6, 15 - r.uniform(2, h - 1), "3")
    return c


def p_idol(r):
    c = canvas()
    for y in np.arange(12, 15.01, 0.25):
        line(c, 4, y, 11, y, "2")
    for y in np.arange(5, 12, 0.25):
        line(c, 6, y, 9, y, "1")
    disc(c, 7.5, 3.5, 1.8, "1")
    line(c, 6, 6, 3, 9, "1"); line(c, 9, 6, 12, 9, "1")
    put(c, 6.8, 3.4, "3"); put(c, 8.2, 3.4, "3")
    return c


def p_candle(r):
    c = canvas()
    for x in (5, 9, 11):
        h = r.uniform(2, 4)
        line(c, x, 15, x, 15 - h, "1"); put(c, x, 14.5 - h, "3")
    return c


def p_altar(r):
    c = canvas()
    for y in np.arange(10, 13, 0.25):
        line(c, 2.5, y, 12.5, y, "1")
    line(c, 3.5, 13, 3.5, 15, "2"); line(c, 11.5, 13, 11.5, 15, "2")
    put(c, 7.5, 9, "3"); line(c, 7.5, 9.5, 7.5, 10, "2")
    return c


def p_panel(r):
    c = canvas()
    for y in np.arange(7, 12, 0.25):
        sh = (12 - y) * 0.6
        line(c, 2 + sh, y, 13 + sh, y, "1")
    for x in np.arange(2, 14, 2.8):
        line(c, x + 3, 7, x, 12, "2")
    line(c, 4.5, 12, 4.5, 15, "2"); line(c, 11, 12, 11, 15, "2")
    put(c, 12, 7.5, "3")
    return c


def p_bed(r):
    c = canvas()
    for y in np.arange(10, 13, 0.25):
        line(c, 2, y, 13, y, "1")
    for y in np.arange(9, 11, 0.25):
        line(c, 2, y, 5, y, "3")
    line(c, 2, 13, 2, 15, "2"); line(c, 13, 13, 13, 15, "2")
    return c


def p_table(r):
    c = canvas()
    line(c, 3, 10, 12, 10, "1"); line(c, 3, 10.5, 12, 10.5, "1")
    line(c, 4, 11, 4, 15, "2"); line(c, 11, 11, 11, 15, "2")
    put(c, 6, 9.5, "3"); put(c, 9, 9.5, "3")
    return c


def p_hive(r):
    c = canvas()
    for k, y0 in enumerate((12, 9, 6)):
        for y in np.arange(y0, y0 + 2.75, 0.25):
            line(c, 4.5, y, 10.5, y, "1" if k % 2 == 0 else "2")
    line(c, 4, 5.5, 11, 5.5, "3")
    line(c, 5, 15, 5, 15, "2"); line(c, 10, 15, 10, 15, "2")
    return c


def p_vat(r):
    c = canvas()
    for y in np.arange(6, 15, 0.25):
        line(c, 4, y, 11, y, "1")
    disc(c, 7.5, 6, 3.5, "3")
    line(c, 11, 8, 14, 8, "2"); line(c, 14, 8, 14, 15, "2")
    return c


def p_obelisk(r):
    c = canvas()
    for y in np.arange(1, 15.01, 0.25):
        w = 1.2 + (y - 1) / 14 * 1.4
        line(c, 7.5 - w, y, 7.5 + w, y, "1")
    for y in np.arange(3, 13, 1.6):
        put(c, 7.5, y, "3")
    line(c, 4, 15, 11, 15, "2")
    return c


def p_pod(r):
    c = canvas()
    for y in np.arange(3, 14, 0.25):
        w = min(3.5, (y - 3) * 0.9)
        line(c, 7.5 - w, y, 7.5 + w, y, "1" if y < 10 else "2")
    line(c, 3, 14, 4, 10, "2"); line(c, 12, 14, 11, 10, "2")
    disc(c, 7.5, 7, 1, "3")
    return c


def p_chute(r):
    c = canvas()
    for x in np.arange(1, 14.5, 0.25):
        y = 13 + math.sin(x * 1.3) * 0.8
        line(c, x, y, x, y + 1.5, "1" if int(x) % 3 else "3")
    return c


def p_crop(r):
    c = canvas()
    for x in np.arange(1.5, 15, 2.5):
        h = r.uniform(2, 5)
        line(c, x, 15, x, 15 - h, "1"); put(c, x - 0.6, 15 - h + 0.5, "3"); put(c, x + 0.6, 15 - h + 1, "3")
    return c


def p_pane(r):
    c = canvas()
    for _ in range(3):
        x, y = r.uniform(2, 12), r.uniform(11, 14)
        line(c, x, y, x + r.uniform(1, 3), y - r.uniform(0, 1), "3")
    return c


def p_boat(r):
    c = canvas()
    for y in np.arange(11, 14, 0.25):
        w = 6 - (y - 11) * 1.2
        line(c, 7.5 - w, y, 7.5 + w, y, "1")
    line(c, 7.5, 11, 7.5, 3, "2")
    for y in np.arange(4, 10, 0.25):
        line(c, 7.5, y, 7.5 + (y - 3) * 0.7, y, "3")
    return c


def p_net(r):
    c = canvas()
    line(c, 2, 15, 2, 5, "2"); line(c, 13, 15, 13, 5, "2"); line(c, 2, 5, 13, 5, "2")
    for x in np.arange(2, 13.5, 1.5):
        line(c, x, 5, x + 1, 12, "1")
    for y in np.arange(6, 12.5, 1.5):
        line(c, 2, y, 13, y, "1")
    return c


def p_scrap(r):
    c = canvas()
    for _ in range(r.integers(7, 12)):
        x, y, w, h = r.uniform(1, 11), r.uniform(6, 13), r.uniform(1.5, 4), r.uniform(1, 2.5)
        ch = "1" if r.random() < 0.5 else "2"
        for yy in np.arange(y, min(15, y + h), 0.25):
            line(c, x, yy, x + w, yy - r.uniform(-0.3, 0.3), ch)
    for _ in range(3):
        put(c, r.uniform(2, 13), r.uniform(6, 13), "3")
    return c


def p_bench(r):
    c = canvas()
    line(c, 2, 11, 13, 11, "1"); line(c, 2, 11.5, 13, 11.5, "1"); line(c, 2, 8, 13, 8, "2")
    line(c, 3, 8, 3, 15, "2"); line(c, 12, 8, 12, 15, "2")
    return c


def p_fence(r):
    c = canvas()
    for x in (2, 13):
        line(c, x, 9, x, 15, "2")
    line(c, 0, 10.5, 15.9, 10.5, "1"); line(c, 0, 13, 15.9, 13, "1")
    return c


def p_satdish(r):
    c = canvas()
    for a in np.linspace(-1.2, 1.2, 50):
        for rr in np.arange(0, 3.6, 0.25):
            put(c, 7.5 + math.sin(a) * rr, 11 - math.cos(a) * rr * 0.5 + rr * 0.3, "1" if rr < 3.4 else "3")
    line(c, 7.5, 12, 7.5, 15, "2")
    return c


# name: (sprite generator, resolution (2 = one cell, 4/6 = big), blocks the way, colours for '1' '2' '3')
PROPS = {
    "mast": (p_mast, 6, True, ("rust", 4), ("rust", 2), ("blood", 6)),
    "dish": (p_dish, 4, True, ("cobble", 5), ("cobble", 2), ("cobble", 6)),
    "dome": (p_dome, 5, True, ("cobble", 5), ("cobble", 3), ("cobble", 6)),
    "tower": (p_tower, 5, True, ("wood", 4), ("wood", 2), ("wood", 5)),
    "watertower": (p_watertower, 5, True, ("rust", 4), ("rust", 2), ("rust", 6)),
    "turbine": (p_turbine, 6, True, ("cobble", 5), ("cobble", 3), ("cobble", 6)),
    "radio": (p_radio, 6, True, ("cobble", 4), ("cobble", 2), ("blood", 6)),
    "logs": (p_logs, 2, True, ("wood", 3), ("wood", 1), ("wood", 5)),
    "stump": (p_stump, 2, True, ("wood", 4), ("wood", 2), ("wood", 5)),
    "tent": (p_tent, 4, True, ("ochre", 4), ("ochre", 2), ("ochre", 1)),
    "rack": (p_rack, 2, True, ("clay", 4), ("wood", 2), ("clay", 5)),
    "crate": (p_crate, 2, True, ("wood", 4), ("wood", 2), ("wood", 5)),
    "barrel": (p_barrel, 2, True, ("rust", 4), ("rust", 1), ("rust", 5)),
    "wagon": (p_wagon, 4, True, ("salt", 4), ("wood", 2), ("wood", 5)),
    "hull": (p_hull, 4, True, ("cobble", 5), ("cobble", 2), ("eye", 6)),
    "debris": (p_debris, 2, False, ("cobble", 4), ("rust", 3), ("cobble", 5)),
    "drill": (p_drill, 6, True, ("rust", 4), ("rust", 2), ("cobble", 5)),
    "cart": (p_cart, 2, True, ("rust", 3), ("rust", 1), ("ochre", 5)),
    "pump": (p_pump, 2, True, ("blood", 3), ("cobble", 2), ("eye", 5)),
    "post": (p_post, 4, True, ("cobble", 4), ("cobble", 2), ("cobble", 5)),
    "car": (p_car, 4, True, ("rust", 4), ("rust", 2), ("ice", 3)),
    "truck": (p_truck, 4, True, ("moss", 3), ("rust", 2), ("ice", 3)),
    "carriage": (p_carriage, 4, True, ("rust", 3), ("cobble", 1), ("eye", 4)),
    "barrier": (p_barrier, 2, True, ("salt", 5), ("cobble", 2), ("blood", 4)),
    "sandbag": (p_sandbag, 2, True, ("ochre", 3), ("ochre", 1), ("ochre", 4)),
    "grave": (p_grave, 2, True, ("stone", 4), ("stone", 2), ("stone", 5)),
    "stone": (p_stone, 5, True, ("stone", 4), ("stone", 2), ("prism", 6)),
    "idol": (p_idol, 4, True, ("stone", 4), ("stone", 2), ("eye", 7)),
    "candle": (p_candle, 2, False, ("salt", 5), ("salt", 3), ("eye", 7)),
    "altar": (p_altar, 2, True, ("stone", 4), ("stone", 2), ("eye", 7)),
    "panel": (p_panel, 2, True, ("frost", 3), ("cobble", 2), ("frost", 6)),
    "bed": (p_bed, 2, True, ("clay", 3), ("wood", 2), ("salt", 5)),
    "table": (p_table, 2, True, ("wood", 4), ("wood", 2), ("salt", 5)),
    "hive": (p_hive, 2, True, ("ochre", 4), ("ochre", 2), ("eye", 5)),
    "vat": (p_vat, 2, True, ("cobble", 4), ("cobble", 2), ("spore", 6)),
    "bones": (weird.g_ribs, 4, True, ("salt", 5), ("salt", 3), ("salt", 6)),
    "obelisk": (p_obelisk, 6, True, ("ash", 1), ("ash", 0), ("prism", 6)),
    "pod": (p_pod, 4, True, ("cobble", 5), ("cobble", 2), ("lava", 6)),
    "chute": (p_chute, 2, False, ("blood", 4), ("blood", 2), ("salt", 6)),
    "crop": (p_crop, 2, False, ("moss", 3), ("moss", 2), ("ochre", 5)),
    "pane": (p_pane, 2, False, ("ice", 5), ("ice", 3), ("ice", 7)),
    "boat": (p_boat, 4, True, ("wood", 4), ("wood", 2), ("salt", 5)),
    "net": (p_net, 2, True, ("salt", 3), ("wood", 2), ("salt", 5)),
    "scrap": (p_scrap, 4, True, ("rust", 4), ("cobble", 3), ("cobble", 6)),
    "bench": (p_bench, 2, True, ("wood", 4), ("wood", 2), ("wood", 5)),
    "fence": (p_fence, 2, True, ("wood", 4), ("wood", 2), ("wood", 5)),
    "satdish": (p_satdish, 2, True, ("cobble", 5), ("cobble", 2), ("cobble", 6)),
    "fire": (None, 2, True, None, None, None),
}
PROP_NAMES = {"mast": "radar mast", "dish": "radar dish", "dome": "radome", "tower": "watchtower", "watertower": "water tower",
              "turbine": "wind turbine", "radio": "radio mast", "logs": "log pile", "stump": "stump", "tent": "tent",
              "rack": "drying rack", "crate": "crate", "barrel": "barrel", "wagon": "wagon", "hull": "piece of hull",
              "drill": "drill rig", "cart": "ore cart", "pump": "fuel pump", "post": "canopy post", "car": "wrecked car",
              "truck": "wrecked truck", "carriage": "train carriage", "barrier": "barrier", "sandbag": "sandbag wall",
              "grave": "gravestone", "stone": "standing stone", "idol": "idol", "altar": "altar", "panel": "solar panel",
              "bed": "bed", "table": "table", "hive": "beehive", "vat": "vat", "bones": "giant rib", "obelisk": "monolith",
              "pod": "drop pod", "boat": "boat", "net": "net", "scrap": "junk heap", "bench": "pew", "fence": "fence",
              "satdish": "satellite dish", "fire": "fire"}

for _n, (_g, _res, *_rest) in PROPS.items():
    if _g is not None:
        weird.GEN["p_" + _n] = _g
        weird.BIG["p_" + _n] = _res
for _n, (_g, _res, _blk, c1, c2, c3) in PROPS.items():
    if _g is not None:
        weird.PROP_COLOURS["p_" + _n] = {"1": F(*c1), "2": F(*c2), "3": F(*c3)}
weird.PROP_COLOURS["p_fire"] = None

BLOCKING = {"p_" + n for n, v in PROPS.items() if v[2]}


# ── layouts ──
L = {}


def layout(name, title, biomes, rows, legend, desc, road=False):
    w = max(len(r) for r in rows)
    L[name] = dict(title=title, biomes=biomes, grid=np.array([list(r.ljust(w)) for r in rows]), legend=legend,
                   desc=desc, road=road)


ANY = None
layout("woodpecker", "an abandoned over-the-horizon radar array", {"tundra", "hills", "grass", "taiga", "drift", "savanna"},
       ["M  M  M  M  M  M  M  M", "ffffffffffffffffffffff", "                      ", "        #####         ",
        "        #.T.#         ", "        #.C.#         ", "        ##+##         "], {"M": "mast", "T": "table", "C": "crate"},
       "A wall of rusted lattice masts marches across the land, humming faintly. Somebody once listened to the whole sky from here.")
layout("radome", "a radar dome station", {"hills", "tundra", "grass", "icesheet", "drift"},
       ["ffffffffff", "f        f", "f   D    f", "f        f", "f  ###   f", "f  #.#   f", "f  #+#  Sf", "ffff  ffff"],
       {"D": "dome", "S": "satdish"}, "A cracked white dome squats inside a sagging fence. Its insides are dark and the door hangs open.")
layout("lumber", "a lumber camp", {"forest", "taiga", "jungle", "swamp"},
       ["L   L   S   S", "             ", "  T    _F_   ", "       ___   ", "S   L      T ", "    S   R    "],
       {"L": "logs", "S": "stump", "T": "tent", "F": "fire", "R": "rack"},
       "Stacked logs, axes left in stumps, tents gone grey with mould. The fire's still warm. Someone left in a hurry.")
layout("hunters", "a hunters' camp", {"forest", "taiga", "savanna", "hills", "tundra", "grass"},
       [" T   R ", "  _F_  ", " C   T "], {"T": "tent", "R": "rack", "F": "fire", "C": "crate"},
       "Hides stretched on racks, a smouldering fire, bones picked clean.")
layout("caravan", "a stopped caravan", {"desert", "savanna", "salt", "badlands", "grass"},
       ["  W   W  ", " W _F_ W ", "  W   W  "], {"W": "wagon", "F": "fire"},
       "Wagons drawn into a ring round a fire. No one is here, but the canvas still flaps.")
layout("shuttle", "a crashed shuttle", ANY,
       ["  d  ***   d ", " d **H*H**  d", "  **H***H*d  ", " d **H**   d ", "   d  ** d   "], {"H": "hull", "d": "debris"},
       "A shuttle came down hard here: torn hull plates, a long scorched furrow, wiring hanging like vines.")
layout("satellite", "a fallen satellite", ANY,
       ["  ***  ", " **A** ", " *dQd* ", "  ***  "], {"A": "satdish", "Q": "panel", "d": "debris"},
       "A satellite lies in its own crater, solar wings snapped, still blinking a tired red light.")
layout("mine", "a derelict mining rig", {"hills", "badlands", "desert", "ash", "tundra"},
       ["   X       ", "  ======== ", "  =   K K  ", "  ======== ", "  C    B B "], {"X": "drill", "K": "cart", "C": "crate", "B": "barrel"},
       "A drill rig stands over a capped shaft. Ore carts sit on rusted rails going nowhere.")
layout("farmstead", "a ruined farmstead", {"grass", "meadow", "savanna"},
       ["%%%%%   ffffffffff", "%,,,%   f::::::::f", "%,B,    f::::::::f", "%%,%%   f::::::::f", "        ffffff fff"],
       {"B": "bed", ":": "crop"}, "A roofless farmhouse and fields gone to seed. The crops grew on without anyone.")
layout("greenhouse", "an overgrown greenhouse", {"grass", "meadow", "forest", "jungle"},
       ["#########", "#:G:::G:#", "#:::G:::#", "#:G:::G:#", "####+####"], {":": "crop", "G": "pane"},
       "Shattered glass panes over beds of something that should not have grown this big.")
layout("radiomast", "a lone radio mast", {"hills", "grass", "tundra", "desert", "savanna"},
       [" s s ", "  R  ", " s s "], {"R": "radio", "s": "sandbag"}, "A single mast with a red light, still blinking out a call sign no one answers.")
layout("bunker", "a sealed bunker", ANY,
       ["sssssss", "s#####s", " #...# ", " #.C.# ", " ##+## ", "  s s  "], {"s": "sandbag", "C": "crate"},
       "A concrete bunker half-buried in the earth. The hatch is open a crack.")
layout("gas", "an old fuel station", {"grass", "desert", "savanna", "badlands", "salt"},
       [" P    P ", "  U  U  ", " P    P ", "        ", "######  ", "#.....# ", "#.CTB.# ", "###+### "],
       {"P": "post", "U": "pump", "C": "crate", "T": "table", "B": "barrel"},
       "Pumps under a collapsed canopy. The shop's been picked clean apart from one stubborn barrel.")
layout("convoy", "a wrecked convoy", ANY, ["V   Y   V", "  Z   Y  "], {"V": "truck", "Y": "car", "Z": "barrier"},
       "Trucks and cars sit nose to tail on the road, doors open, a barrier dragged across ahead of them.", road=True)
layout("watchtower", "a watchtower", {"forest", "grass", "hills", "savanna", "taiga"},
       ["fffffff", "f     f", "f  O  f", "f   F f", "fff fff"], {"O": "tower", "F": "fire"},
       "A wooden tower over a fenced yard, with a good view of everything coming.")
layout("cemetery", "a cemetery", {"grass", "meadow", "forest", "swamp", "hills"},
       ["ffffffffff", "f g g g gf", "f        f", "f g g g gf", "f   X    f", "ffff ffff "], {"g": "grave", "X": "stump"},
       "Rows of worn headstones. The names have weathered away, every one.")
layout("stones", "a stone circle", {"grass", "hills", "meadow", "tundra", "crystal", "salt"},
       ["  O O  ", "O     O", "   A   ", "O     O", "  O O  "], {"O": "stone", "A": "altar"},
       "Standing stones in a ring, older than anything else here. The air hums between them.")
layout("shrine", "a jungle shrine", {"jungle", "fungal", "crystal", "swamp", "forest"},
       [" c I c ", "  _A_  ", " c _ c "], {"I": "obelisk", "A": "altar", "c": "candle"},
       "A strange idol watches over an altar. The candles are lit. Fresh offerings.")
layout("solar", "a solar farm", {"desert", "salt", "savanna", "badlands"},
       ["QQQQ QQQQ", "         ", "QQQQ QQQQ", "         ", "QQQQ QQQQ"], {"Q": "panel"},
       "Rows of dusty solar panels, still tracking the sun with a faint grinding.")
layout("windfarm", "a wind farm", {"grass", "hills", "tundra", "savanna", "beach"},
       ["N    N    N", "           ", "     N     "], {"N": "turbine"}, "Huge turbines turn slowly over the land. One has lost a blade.")
layout("watertower", "a water tower", {"grass", "desert", "savanna", "badlands"},
       ["  J  ", " B B "], {"J": "watertower", "B": "barrel"}, "A rusted water tower on spindly legs. It still sloshes.")
layout("scrapyard", "a scrapyard", {"badlands", "desert", "ash", "grass", "salt"},
       ["ffffffffff", "f J  Y  Jf", "f  Y   J f", "f J   Y  f", "fffff ffff"], {"J": "scrap", "Y": "car"},
       "Heaps of junk and gutted cars behind a fence. A good place to find parts.")
layout("outpost", "a research outpost", {"tundra", "icesheet", "crystal", "ash", "desert", "salt"},
       ["#####  #####", "#...#  #...#", "#.T.++++.C.#", "#####  #####", "   A    A   "], {"T": "table", "C": "crate", "A": "satdish"},
       "Prefab research modules joined by a walkway. Notes still pinned to the walls, all saying 'don't'.")
layout("fishing", "a fishing shack", {"beach", "swamp"},
       [" www  ", " w,w n", " w+w  ", "   b n"], {"n": "net", "b": "boat"}, "A tarred shack with nets out to dry and a boat pulled up beside it.")
layout("train", "a derailed train", {"grass", "desert", "savanna", "badlands", "tundra", "hills"},
       ["================", " U   U   U   U  ", "================"], {"U": "carriage"},
       "A train lies across its own tracks, carriages split open. Cargo everywhere.")
layout("checkpoint", "a military checkpoint", ANY,
       ["ss    ss", "s####  s", " #..#   ", " #+##   ", "Z      Z"], {"s": "sandbag", "Z": "barrier"},
       "Sandbags, barriers and a guard hut. Whoever held it isn't holding it now.")
layout("cabin", "a woodland cabin", {"forest", "taiga", "swamp", "hills"},
       ["wwwwww", "w,,B,w", "w,T,,w", "w,,,,w", "ww+www", "  F   "], {"B": "bed", "T": "table", "F": "fire"},
       "A snug cabin with a fire outside, a made bed and a cold meal on the table.")
layout("apiary", "an apiary", {"meadow", "grass"},
       ["fffffff", "f h h f", "f h h f", "fff fff"], {"h": "hive"}, "Beehives in a fenced patch. Something much bigger than a bee is buzzing.")
layout("shroomfarm", "a spore farm", {"fungal", "swamp", "jungle"},
       [" V V V ", " ::::: ", " V V V "], {"V": "vat", ":": "crop"}, "Vats of glowing culture and rows of fat mushrooms. Someone was farming these.")
layout("skeleton", "the bones of something huge", {"desert", "salt", "ash", "badlands", "tundra"},
       ["  KKK  ", " K K K ", "  KKK  "], {"K": "bones"}, "Ribs as tall as trees arch out of the ground. It died a very long time ago.")
layout("monolith", "a black monolith", ANY, ["  *  ", " *O* ", "  *  "], {"O": "obelisk"},
       "A perfectly black slab. The ground round it is scorched in a perfect ring. The glyphs on it are warm.")
layout("droppod", "a supply drop pod", ANY, [" ccc ", "*P*  ", " **  "], {"P": "pod", "c": "chute"},
       "A drop pod, its parachute trailing. The hatch has already been forced.")
layout("chapel", "a ruined chapel", {"grass", "meadow", "forest", "hills"},
       ["%%%#%%%", "%.....%", "%.L.L.%", "%..A..%", "%.L.L.%", "%%%+%%%"], {"L": "bench", "A": "altar"},
       "The roof fell in long ago. The pews still face the altar.")

CELL = {"#": "wall", "w": "wwall", "%": "ruin", ".": "floor", ",": "wfloor", "_": "packed", "*": "scorch", "+": "floor",
        "~": "mosaic"}
NOT_ON = {"deep", "ocean", "shallow", "lake", "river", "bridge", "house", "plaza", "street", "hcarpet", "hcarpetb",
          "hlino", "hbath", "hconc", "gdoor", "hwall", "hwin", "hdoor", "hfloor", "bonfire", "lava", "mountain", "peak",
          "volcano", "seaice"}


def _rng(*parts):
    return np.random.default_rng(zlib.crc32(":".join(map(str, parts)).encode()))


def pick_layout(wd, cx, cy):
    """which structure (if any) stands in world square (cx, cy): (name, rotation, mirror, x0, y0) in a 40x40 zone"""
    r = _rng(wd.seed, "struct", cx, cy)
    if r.random() > 0.26 or (cx, cy) in wd.towns:
        return None
    b = str(wd.biome[cy, cx])
    if b in NOT_ON or b in ("deep", "ocean", "shallow", "lake"):
        return None
    on_road = any((cx, cy) in (a, c) for a, c in wd.dlinks)
    cands = [n for n, d in L.items() if (d["biomes"] is None or b in d["biomes"]) and (not d["road"] or on_road)]
    if not cands:
        return None
    if on_road and "convoy" in cands and r.random() < 0.3:
        name = "convoy"
    else:
        name = cands[r.integers(len(cands))]
    return name, int(r.integers(4)), bool(r.random() < 0.5), r


def stamp(b, name, rot, mirror, r, zw, zh, near=None):
    """press a layout into the zone's cells. near = (x, y) to centre on (e.g. a road), else somewhere open"""
    g = L[name]["grid"]
    g = np.rot90(g, rot)
    if mirror:
        g = np.fliplr(g)
    h, w = g.shape
    if near is None:
        x0, y0 = int(r.integers(3, max(4, zw - w - 3))), int(r.integers(3, max(4, zh - h - 3)))
    else:
        x0, y0 = int(np.clip(near[0] - w // 2, 1, zw - w - 1)), int(np.clip(near[1] - h // 2, 1, zh - h - 1))
    legend = L[name]["legend"]
    for j in range(h):
        for i in range(w):
            ch = g[j, i]
            if ch == " ":
                continue
            x, y = x0 + i, y0 + j
            if not (0 <= x < zw and 0 <= y < zh) or str(b[y, x]) in NOT_ON:
                continue
            if ch == "=":
                b[y, x] = "railh" if rot % 2 == 0 else "railv"
            elif ch == "f":
                b[y, x] = "p_fence"
            elif ch in CELL:
                b[y, x] = CELL[ch]
            elif ch in legend:
                b[y, x] = "p_" + legend[ch]
    return (x0, y0, w, h)


def place(wd, b, cx, cy, zw, zh):
    """called while a zone is being made: maybe put a structure in it"""
    hit = pick_layout(wd, cx, cy)
    if not hit:
        return None
    name, rot, mirror, r = hit
    near = None
    if L[name]["road"]:
        ys, xs = np.nonzero(b == "road")
        if not len(ys):
            return None
        k = len(ys) // 2
        near = (int(xs[k]), int(ys[k]))
    stamp(b, name, rot, mirror, r, zw, zh, near)
    return name


def describe(wd, cx, cy):
    hit = pick_layout(wd, cx, cy)
    if not hit:
        return None
    d = L[hit[0]]
    return f"You come across {d['title']}. {d['desc']}"


import cultures  # noqa: E402,F401  (Aztec / Egyptian / Soviet / rural / alien ruins and relics register themselves)
