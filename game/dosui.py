"""An MS-DOS text-mode screen for menus: 80 x 25 characters of 8 x 16 pixels in the 16 VGA colours, drawn at
640 x 400 and scaled up with hard pixel edges. Box-drawing borders, CP437-style symbols."""
import os
import pygame

VGA = {"black": (0, 0, 0), "blue": (0, 0, 170), "green": (0, 170, 0), "cyan": (0, 170, 170), "red": (170, 0, 0),
       "magenta": (170, 0, 170), "brown": (170, 85, 0), "grey": (170, 170, 170), "dgrey": (85, 85, 85),
       "lblue": (85, 85, 255), "lgreen": (85, 255, 85), "lcyan": (85, 255, 255), "lred": (255, 85, 85),
       "lmagenta": (255, 85, 255), "yellow": (255, 255, 85), "white": (255, 255, 255)}
COLS, ROWS, CW, CH = 80, 25, 8, 16
import fonts
FONTS = [fonts.find(fonts.PIXEL), fonts.find(fonts.MONO), fonts.find(fonts.MONO2)]


class Dos:
    def __init__(self, cols=COLS, rows=ROWS):
        self.cols, self.rows = cols, rows                 # 80 x 25 on the PC; tall and narrow on a phone
        path = next((p for p in FONTS if os.path.exists(p)), None)
        self.font = pygame.font.Font(path, 16 if path and "Proggy" in path else 13)
        sym = next((p for p in FONTS[1:] if os.path.exists(p)), path)
        self.symbols = pygame.font.Font(sym, 13)
        self.surf = pygame.Surface((cols * CW, rows * CH))
        self.cache = {}

    # box-drawing: which sides each piece reaches, and whether it's double. Drawn as exact pixels, like VGA.
    BOX = {"─": ("lr", 1), "│": ("ud", 1), "┌": ("rd", 1), "┐": ("ld", 1), "└": ("ru", 1), "┘": ("lu", 1),
           "═": ("lr", 2), "║": ("ud", 2), "╔": ("rd", 2), "╗": ("ld", 2), "╚": ("ru", 2), "╝": ("lu", 2)}

    def glyph(self, ch, fg):
        k = (ch, fg)
        if k not in self.cache:
            col = VGA.get(fg, fg) if isinstance(fg, str) else fg
            cell = pygame.Surface((CW, CH), pygame.SRCALPHA)
            if ch in self.BOX:
                sides, n = self.BOX[ch]
                mx, my = CW // 2, CH // 2
                offs = (0,) if n == 1 else (-2, 1)
                for o in offs:                                  # each line (two for double), out to its sides
                    if "l" in sides or "r" in sides:
                        x0 = 0 if "l" in sides else mx + (min(offs) if n == 2 and "d" in sides and o == offs[0] else 0)
                        x1 = CW if "r" in sides else mx + 1
                        if n == 2 and len(sides) == 2 and sides[1] in "ud":   # corners: inner line shorter
                            inner = (o == offs[1]) == (sides[1] == "d")
                            if "r" in sides:
                                x0 = mx + (offs[1] if inner else offs[0])
                            else:
                                x1 = mx + 1 + (offs[0] if inner else offs[1])
                        pygame.draw.line(cell, col, (x0, my + o), (x1 - 1, my + o))
                    if "u" in sides or "d" in sides:
                        y0 = 0 if "u" in sides else my
                        y1 = CH if "d" in sides else my + 1
                        if n == 2 and len(sides) == 2 and sides[0] in "lr":
                            inner = (o == offs[1]) == (sides[0] == "r")
                            if "d" in sides:
                                y0 = my + (offs[1] if inner else offs[0])
                            else:
                                y1 = my + 1 + (offs[0] if inner else offs[1])
                        pygame.draw.line(cell, col, (mx + o, y0), (mx + o, y1 - 1))
            else:
                f = self.font if ord(ch) < 128 else self.symbols   # letters from the pixel font, symbols from DejaVu
                img = f.render(ch, False, col)                  # no smoothing: DOS
                cell.blit(img, ((CW - img.get_width()) // 2, (CH - img.get_height()) // 2))
            self.cache[k] = cell
        return self.cache[k]

    def clear(self, bg="black"):
        self.surf.fill(VGA[bg])

    def put(self, x, y, text, fg="grey", bg=None):
        for i, ch in enumerate(text):
            if 0 <= x + i < self.cols and 0 <= y < self.rows:
                if bg:
                    pygame.draw.rect(self.surf, VGA[bg], ((x + i) * CW, y * CH, CW, CH))
                if ch != " ":
                    self.surf.blit(self.glyph(ch, fg), ((x + i) * CW, y * CH))

    def fill(self, x, y, w, h, bg):
        pygame.draw.rect(self.surf, VGA[bg], (x * CW, y * CH, w * CW, h * CH))

    def box(self, x, y, w, h, fg="grey", bg="black", title=None):
        """a double-line box, cleared inside"""
        self.fill(x, y, w, h, bg)
        self.put(x, y, "╔" + "═" * (w - 2) + "╗", fg, bg)
        for j in range(1, h - 1):
            self.put(x, y + j, "║", fg, bg)
            self.put(x + w - 1, y + j, "║", fg, bg)
        self.put(x, y + h - 1, "╚" + "═" * (w - 2) + "╝", fg, bg)
        if title:
            self.put(x + 2, y, f" {title} ", "white", bg)

    def blit_to(self, screen, area=None):
        """scale up to fill the screen (or area, a Rect), keeping the shape: hard pixel edges, black bars"""
        area = pygame.Rect(area or screen.get_rect())
        k = min(area.w / self.surf.get_width(), area.h / self.surf.get_height())
        w, h = int(self.surf.get_width() * k), int(self.surf.get_height() * k)
        screen.fill((0, 0, 0), area)
        x0, y0 = area.x + (area.w - w) // 2, area.y + (area.h - h) // 2 if area.h > h + 2 else area.y
        screen.blit(pygame.transform.scale(self.surf, (w, h)), (x0, y0))
        return (x0, y0, k)

    def cell_at(self, pos, place):
        ox, oy, k = place
        return int((pos[0] - ox) / k) // CW, int((pos[1] - oy) / k) // CH
