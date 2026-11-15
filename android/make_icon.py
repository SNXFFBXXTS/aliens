"""the app icon: a red-eyed head kanji on black"""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "game"))
import pygame
import fonts
pygame.init()
s = pygame.Surface((512, 512))
s.fill((10, 9, 14))
pygame.draw.circle(s, (90, 12, 12), (256, 256), 230)
f = pygame.font.Font(fonts.find(fonts.CJK), 330)
g = f.render("眼", True, (255, 60, 50))
s.blit(g, g.get_rect(center=(256, 250)))
pygame.image.save(s, sys.argv[1])
