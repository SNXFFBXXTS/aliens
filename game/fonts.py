"""Where the fonts are. On the PC they come from the system; the Android build carries copies in game/fonts/
(android/build.sh puts them there). find() prefers a bundled copy, then the system path."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLED = os.path.join(HERE, "fonts")

CJK = "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"
UI = "/usr/share/fonts/noto/NotoSans-Regular.ttf"
UIB = "/usr/share/fonts/noto/NotoSans-Bold.ttf"
SERIF = "/usr/share/fonts/noto/NotoSerif-BoldItalic.ttf"
PIXEL = os.path.expanduser("~/.local/share/fonts/ProggyCleanNerdFontMono-Regular.ttf")
MONO = "/usr/share/fonts/TTF/DejaVuSansMono.ttf"
MONO2 = "/usr/share/fonts/noto/NotoSansMono-Regular.ttf"
ALL = (CJK, UI, UIB, SERIF, PIXEL, MONO, MONO2)


def find(path):
    """the bundled copy of a font if there is one, else the system one (which may not exist: callers check)"""
    b = os.path.join(BUNDLED, os.path.basename(path))
    return b if os.path.exists(b) else path
