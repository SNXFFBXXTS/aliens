"""Phone mode: an upright screen with touch controls (a joystick on the left, buttons on the right).

On by itself on Android; on the PC try it with  rl --phone  (the mouse stands in for your finger).
The buttons just press the game's own keys, so everything works the same as on the PC.
"""
import math
import os
import sys
import time

import pygame

ANDROID = "ANDROID_ARGUMENT" in os.environ or hasattr(sys, "getandroidapilevel")
ON = ANDROID or "--phone" in sys.argv
SIZE = (450, 1000)                    # the game draws at this size; it's scaled up to fill the phone's screen
PANEL_H = 250                         # the touch controls along the bottom
HUD_H = 56                            # the bars along the top (two rows)
LOG_H = PANEL_H + 76                  # messages + controls
STICK_R = 86


def press(k, u=""):
    return pygame.event.Event(pygame.KEYDOWN, key=k, unicode=u, mod=0)


def pointer(e, screen):
    """(pointer id, x, y in the game's own pixels) for a touch or mouse event; "skip" for a touch the mouse is
    copying (the finger event has it already); None for anything else"""
    if e.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
        sw, sh = screen.get_size()
        try:
            ww, wh = pygame.display.get_window_size()
        except Exception:
            ww, wh = sw, sh
        k = min(ww / sw, wh / sh)                         # the game is scaled up and centred in the window
        ox, oy = (ww - sw * k) / 2, (wh - sh * k) / 2
        return ("f", e.finger_id), (e.x * ww - ox) / k, (e.y * wh - oy) / k
    if e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
        if getattr(e, "touch", False):
            return "skip"
        if e.type == pygame.MOUSEMOTION and not e.buttons[0]:
            return None
        if e.type != pygame.MOUSEMOTION and e.button != 1:
            return None
        return ("m", 0), e.pos[0], e.pos[1]
    return None


class Controls:
    def __init__(self, game):
        self.g = game
        self.stick = (0.0, 0.0)       # where the joystick is pushed: -1..1 each way
        self.stick_id = None          # which finger (or the mouse) is on it
        self.lit = {}                 # button label -> when it was last pressed (it lights up)
        self.map_step = 0.0
        self.font = game.load_font(15, True)
        self.small = game.load_font(11)

    # ── layout ──
    def panel(self):
        sw, sh = self.g.screen.get_size()
        return pygame.Rect(0, sh - PANEL_H, sw, PANEL_H)

    def stick_centre(self):
        p = self.panel()
        return p.x + 112, p.y + PANEL_H // 2

    def actions(self):
        """the buttons for what's on screen now: [(label, key, unicode)]"""
        g = self.g
        K = pygame
        back = ("Back", K.K_q, "q")
        if g.dead:
            return [("Wake up", K.K_RETURN, "\r")]
        if g.detail:
            kind = __import__("items").ITEMS[g.detail][1]
            use = {"food": ("Eat", "e"), "drink": ("Drink", "e"), "medical": ("Use", "a"),
                   "weapon": ("Hold" if g.weapon != g.detail else "Put away", "w")}.get(kind)
            return ([(use[0], 0, use[1])] if use else []) + [("Drop", K.K_d, "d"), back]
        if g.loot:
            if g.mode == "take":
                return [("All", 0, ","), ("Take", K.K_RETURN, "\r"), ("Put in", K.K_TAB, "\t"), back]
            return [("Put in", K.K_RETURN, "\r"), ("Take out", K.K_TAB, "\t"), back]
        if g.show_inv or getattr(g, "outfit", False) or getattr(g, "build_menu", False):
            return [back]
        if getattr(g, "placing", None) is not None:
            return [("Build", K.K_RETURN, "\r"), ("Take down", K.K_x, "x"), ("List", K.K_b, "b"), back]
        if g.show_map:
            return [back]
        return [("Head", K.K_f, "f"), ("Use", K.K_e, "e"), ("Bag", K.K_i, "i"),
                ("Outfit", K.K_c, "c"), ("Build", K.K_b, "b"), ("Wood", K.K_g, "g"),
                ("Map", K.K_m, "m"), ("Zoom −", K.K_MINUS, "-"), ("Zoom +", K.K_EQUALS, "=")]

    def button_rects(self):
        p = self.panel()
        acts = self.actions()
        x0, w = 222, p.w - 222 - 8
        cols = 3 if len(acts) > 4 else 2 if len(acts) > 1 else 1
        rows = math.ceil(len(acts) / cols)
        bw, bh = w // cols, min(78, (PANEL_H - 16) // rows)
        top = p.y + (PANEL_H - bh * rows) // 2
        return [(a, pygame.Rect(x0 + (i % cols) * bw + 3, top + (i // cols) * bh + 3, bw - 6, bh - 6))
                for i, a in enumerate(acts)]

    def stick_used(self):
        g = self.g
        return not (g.dead or g.detail or g.loot or g.show_inv or getattr(g, "outfit", False) or
                    getattr(g, "build_menu", False))

    # ── input ──
    def to_screen(self, e):
        return pointer(e, self.g.screen)

    def handle(self, e):
        """True if the controls used the event (the game shouldn't see it)"""
        g = self.g
        if e.type == pygame.KEYDOWN and e.key == pygame.K_AC_BACK:   # Android's back button: close what's open
            g.handle(press(pygame.K_q, "q"))
            return True
        if e.type == pygame.MOUSEWHEEL:
            return False
        got = self.to_screen(e)
        if got == "skip":
            return True
        if got is None:
            return False
        pid, x, y = got
        down = e.type in (pygame.FINGERDOWN, pygame.MOUSEBUTTONDOWN)
        up = e.type in (pygame.FINGERUP, pygame.MOUSEBUTTONUP)
        if getattr(g, "cold_open", None):
            if down:
                g.handle(press(pygame.K_SPACE, " "))
            return True
        if pid == self.stick_id:
            if up:
                self.stick_id, self.stick = None, (0.0, 0.0)
            else:
                self.push(x, y)
            return True
        if not down:
            return True
        if self.panel().collidepoint(x, y):
            cx, cy = self.stick_centre()
            if self.stick_used() and math.hypot(x - cx, y - cy) < STICK_R + 30:
                self.stick_id = pid
                self.push(x, y)
                return True
            for (label, k, u), r in self.button_rects():
                if r.inflate(6, 6).collidepoint(x, y):
                    self.lit[label] = time.monotonic()
                    if k == pygame.K_f:                    # the head goes where you're walking
                        g.use_head()
                    else:
                        g.handle(press(k, u))
                    return True
            return True
        # above the controls
        if g.detail:
            return True
        if g.show_inv or g.loot or getattr(g, "outfit", False) or getattr(g, "build_menu", False):
            place = getattr(g, "_dos_place", None)
            if place and hasattr(g, "dos"):
                ox, oy, k = place
                row = int((y - oy) / k) // 16
                u = getattr(g, "_tap_rows", {}).get(row)
                if u:
                    g.handle(press(0, u))
            return True
        if g.show_map or g.dead or getattr(g, "placing", None) is not None:
            return True
        cam = getattr(g, "_cam", None)                      # a tap in the world: your head goes there
        if cam:
            import rl
            cxp, cyp, kx, ky, top = cam
            g.use_head(((x * kx + cxp) / rl.PX, ((y - rl.HUD_H) * ky + cyp) / rl.PX))
        return True

    def push(self, x, y):
        cx, cy = self.stick_centre()
        dx, dy = (x - cx) / STICK_R, (y - cy) / STICK_R
        n = math.hypot(dx, dy)
        if n > 1:
            dx, dy = dx / n, dy / n
        self.stick = (dx, dy) if n > 0.18 else (0.0, 0.0)

    def tick(self, dt):
        """every frame: the joystick moves the map cursor while the map is open"""
        g = self.g
        sx, sy = self.stick
        if g.show_map and (abs(sx) > 0.4 or abs(sy) > 0.4):
            self.map_step -= dt
            if self.map_step <= 0:
                self.map_step = 0.12
                k = (pygame.K_RIGHT if sx > 0.4 else pygame.K_LEFT) if abs(sx) >= abs(sy) else \
                    (pygame.K_DOWN if sy > 0.4 else pygame.K_UP)
                g.handle(press(k))
        else:
            self.map_step = 0.0

    def direction(self):
        """the joystick as walking input: (ix, iy, how hard 0..1), or None if it's not pushed"""
        sx, sy = self.stick
        n = math.hypot(sx, sy)
        return (sx / n, sy / n, min(1.0, n / 0.8)) if n else None

    # ── drawing ──
    def draw(self):
        g = self.g
        S = g.screen
        p = self.panel()
        pygame.draw.rect(S, (12, 10, 16), p)
        pygame.draw.line(S, (60, 54, 70), p.topleft, p.topright, 1)
        if self.stick_used():
            cx, cy = self.stick_centre()
            pygame.draw.circle(S, (30, 27, 38), (cx, cy), STICK_R)
            pygame.draw.circle(S, (80, 72, 96), (cx, cy), STICK_R, 2)
            for a in range(4):                             # little arrows round the edge
                ang = a * math.pi / 2
                ax, ay = cx + math.cos(ang) * (STICK_R - 16), cy + math.sin(ang) * (STICK_R - 16)
                pygame.draw.circle(S, (90, 82, 106), (int(ax), int(ay)), 4)
            kx, ky = cx + self.stick[0] * STICK_R * 0.7, cy + self.stick[1] * STICK_R * 0.7
            pygame.draw.circle(S, (150, 140, 170) if self.stick_id else (110, 100, 130), (int(kx), int(ky)), 34)
            pygame.draw.circle(S, (200, 190, 220), (int(kx), int(ky)), 34, 2)
            lab = self.small.render("move" if not g.show_map else "look", True, (120, 112, 135))
            S.blit(lab, (cx - lab.get_width() // 2, p.bottom - 18))
        now = time.monotonic()
        for (label, k, u), r in self.button_rects():
            lit = now - self.lit.get(label, 0) < 0.15
            col = (70, 62, 88) if not lit else (150, 130, 90)
            edge = (120, 110, 140)
            txt = label
            if label == "Head" and g.char:                  # shows if your head is ready
                import heads
                left_ = g.head_ready - now
                ready = not g.head_out and left_ <= 0
                col = (120, 40, 40) if ready and g.headinfo["power"] == "scout" else (96, 80, 50) if ready else (40, 36, 48)
                edge = (240, 220, 160) if ready else (90, 84, 100)
                txt = heads.POWERS[g.headinfo["power"]]["name"] if ready else ("out" if g.head_out else f"{left_:.1f}s")
            pygame.draw.rect(S, col, r, border_radius=10)
            pygame.draw.rect(S, edge, r, 2, border_radius=10)
            f = self.font if self.font.size(txt)[0] < r.w - 8 else self.small
            img = f.render(txt, True, (240, 236, 228))
            S.blit(img, (r.centerx - img.get_width() // 2, r.centery - img.get_height() // 2))
