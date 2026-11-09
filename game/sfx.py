"""Little sound effects from a tiny wavetable + FM synth, in the spirit of old RuneScape's synth:
each sound is a few voices, each a wavetable oscillator (sine / square / saw / noise) with a pitch envelope,
a volume envelope, an FM modulator (its own rate and depth envelope), optional tremolo, then a short echo.
Everything is made once with numpy and written as small .wav files.
"""
import numpy as np

RATE = 22050
TABLE = 2048
_ph = np.arange(TABLE) / TABLE
TABLES = {
    "sine": np.sin(2 * np.pi * _ph),
    "square": np.where(_ph < 0.5, 1.0, -1.0),
    "saw": 2 * _ph - 1,
    "tri": 1 - 4 * np.abs(_ph - 0.5),
}


def env(points, n):
    """piecewise-linear envelope from [(time 0..1, value), ...] over n samples"""
    ts, vs = zip(*points)
    return np.interp(np.linspace(0, 1, n), ts, vs)


def voice(dur, wave="sine", freq=((0, 440), (1, 440)), amp=((0, 0), (0.02, 1), (1, 0)),
          fm_rate=0.0, fm_depth=((0, 0), (1, 0)), trem=0.0, start=0.0, seed=0):
    """one oscillator, dur seconds long, placed at `start` seconds"""
    n = int(dur * RATE)
    f = env(freq, n)
    if fm_rate:                                            # FM: wobble the pitch with a sine at fm_rate
        k = np.arange(n) / RATE
        f = f * (1 + env(fm_depth, n) * np.sin(2 * np.pi * fm_rate * k))
    if wave == "noise":                                    # noise "wavetable": sample-and-hold at the pitch
        rng = np.random.default_rng(seed)
        steps = np.cumsum(f / RATE)
        idx = steps.astype(np.int64)
        x = rng.uniform(-1, 1, idx[-1] + 2)[idx] if n else np.zeros(0)
    else:
        phase = np.cumsum(f / RATE) % 1.0
        x = TABLES[wave][(phase * TABLE).astype(np.int64) % TABLE]
    a = env(amp, n)
    if trem:
        a = a * (0.75 + 0.25 * np.sin(2 * np.pi * trem * np.arange(n) / RATE))
    return int(start * RATE), x * a


def mix(*voices, echo=0.0, echo_gain=0.3, crush=0):
    end = max(s + len(x) for s, x in voices)
    out = np.zeros(end + int(echo * RATE * 3) + 1)
    for s, x in voices:
        out[s:s + len(x)] += x
    if echo:                                               # a couple of soft repeats
        d = int(echo * RATE)
        for k in (1, 2):
            out[d * k:] += out[:len(out) - d * k] * echo_gain ** k
    if crush:                                              # a touch of 8-bit grit
        out = np.round(out * crush) / crush
    return out


def sounds():
    """name -> samples (float, roughly -1..1)"""
    S = {}
    # wooden cupboard / drawer: a creak (FM-wobbled square sliding down), then a soft knock
    S["open_wood"] = mix(
        voice(0.32, "square", freq=((0, 340), (0.6, 210), (1, 190)), amp=((0, 0), (0.1, 0.35), (0.8, 0.25), (1, 0)),
              fm_rate=23, fm_depth=((0, 0.08), (1, 0.03))),
        voice(0.08, "noise", freq=((0, 1800), (1, 600)), amp=((0, 0.9), (1, 0)), start=0.3, seed=1),
        voice(0.12, "sine", freq=((0, 130), (1, 90)), amp=((0, 0.8), (1, 0)), start=0.3),
        echo=0.07, crush=48)
    # metal door / drum: a clunk and an inharmonic ring (FM at a non-integer ratio)
    S["open_metal"] = mix(
        voice(0.06, "noise", freq=((0, 4000), (1, 900)), amp=((0, 1), (1, 0)), seed=2),
        voice(0.5, "sine", freq=((0, 520), (1, 500)), amp=((0, 0), (0.01, 0.5), (1, 0)),
              fm_rate=520 * 1.41, fm_depth=((0, 0.6), (1, 0.05))),
        voice(0.18, "square", freq=((0, 95), (1, 70)), amp=((0, 0.5), (1, 0))),
        echo=0.09, crush=48)
    # rummaging: little filtered noise rustles over a second
    rng = np.random.default_rng(5)
    S["rummage"] = mix(*[voice(rng.uniform(0.04, 0.09), "noise",
                               freq=((0, rng.uniform(900, 2400)), (1, rng.uniform(400, 900))),
                               amp=((0, 0), (0.2, rng.uniform(0.25, 0.5)), (1, 0)), start=t, seed=int(t * 100))
                         for t in np.sort(rng.uniform(0, 0.9, 9))], crush=40)
    # found something: a bright two-note FM blip, rising
    S["found"] = mix(
        voice(0.09, "square", freq=((0, 660), (1, 660)), amp=((0, 0), (0.05, 0.45), (1, 0)), fm_rate=30,
              fm_depth=((0, 0.02), (1, 0.02))),
        voice(0.22, "square", freq=((0, 990), (1, 1000)), amp=((0, 0), (0.03, 0.45), (1, 0)), start=0.08,
              fm_rate=1990, fm_depth=((0, 0.3), (1, 0))),
        echo=0.06, crush=32)
    # nothing there: a low falling blip
    S["empty"] = mix(voice(0.22, "tri", freq=((0, 240), (1, 150)), amp=((0, 0), (0.05, 0.6), (1, 0))), crush=32)
    # moving an item between bag and container: a tiny click-blip
    S["take"] = mix(voice(0.05, "square", freq=((0, 880), (1, 1320)), amp=((0, 0.4), (1, 0))),
                    voice(0.03, "noise", freq=((0, 3000), (1, 3000)), amp=((0, 0.3), (1, 0)), seed=3), crush=32)
    # eating: three soft crunchy bites
    S["eat"] = mix(*[voice(0.06, "noise", freq=((0, 1400), (1, 500)), amp=((0, 0.7), (1, 0)), start=t, seed=9 + i)
                     for i, t in enumerate((0, 0.16, 0.32))], crush=40)
    # drinking: glugs, an FM-wobbled sine bubbling upwards
    S["drink"] = mix(*[voice(0.1, "sine", freq=((0, 260 + i * 30), (1, 420 + i * 30)), amp=((0, 0), (0.2, 0.6), (1, 0)),
                             fm_rate=40, fm_depth=((0, 0.2), (1, 0.05)), start=i * 0.14) for i in range(3)])
    # bandaging / medkit: a cloth rip then a soft chime
    S["heal"] = mix(voice(0.18, "noise", freq=((0, 5000), (1, 2500)), amp=((0, 0.5), (1, 0)), seed=11),
                    voice(0.4, "sine", freq=((0, 784), (1, 784)), amp=((0, 0), (0.05, 0.35), (1, 0)), start=0.15,
                          fm_rate=784 * 2, fm_depth=((0, 0.15), (1, 0))), echo=0.08)
    # readying a weapon: a short metallic shing
    S["equip"] = mix(voice(0.25, "saw", freq=((0, 1800), (1, 2600)), amp=((0, 0), (0.05, 0.3), (1, 0)),
                           fm_rate=2600 * 1.5, fm_depth=((0, 0.2), (1, 0))), crush=48)
    # cold-open sting: a brassy three-hit jazz stab (FM at ratio 1 sounds like brass), walking bass, a hi-hat
    def stab(t, root, dur):
        return [voice(dur, "saw", freq=((0, root * r), (1, root * r)), amp=((0, 0), (0.04, 0.32), (0.5, 0.2), (1, 0)),
                      fm_rate=root * r, fm_depth=((0, 0.5), (0.3, 0.15), (1, 0.05)), start=t) for r in (1, 1.26, 1.5, 1.78)]
    S["sting"] = mix(*stab(0.0, 233, 0.16), *stab(0.22, 233, 0.12), *stab(0.42, 277, 0.7),
                     *[voice(0.22, "tri", freq=((0, f), (1, f)), amp=((0, 0.7), (1, 0)), start=t)
                       for t, f in ((0, 58), (0.22, 69), (0.42, 78), (0.64, 87))],
                     *[voice(0.04, "noise", freq=((0, 8000), (1, 8000)), amp=((0, 0.25), (1, 0)), start=t, seed=20 + i)
                       for i, t in enumerate((0, 0.11, 0.22, 0.33, 0.42))],
                     echo=0.12, echo_gain=0.25, crush=64)
    return S
