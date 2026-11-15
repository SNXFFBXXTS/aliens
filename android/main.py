"""The Android app starts here: saves go in the app's own storage, then the game runs in phone mode."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("RL_HOME", os.path.join(os.environ.get("ANDROID_PRIVATE", HERE), "saves"))
sys.path.insert(0, HERE)

import rl  # noqa: E402

rl.main()
