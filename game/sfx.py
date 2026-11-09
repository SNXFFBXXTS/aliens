"""Sound, made from noise and sine waves (no chip-tune beeps): grainy gusting wind, whistles through gaps,
faint detuned drones, and foley for what you do (creaks, scrapes, rustles, glugs). Made once with numpy.
"""
import numpy as np

RATE = 22050


def band(n, lo, hi, rng, soft=0.25):
    """white noise kept only between lo and hi Hz (soft edges), normalised"""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / RATE)
    w = lambda x, edge: 0.5 * (1 + np.tanh((x - edge) / max(1.0, edge * soft)))
    spec *= w(f, lo) * (1 - w(f, hi))
    x = np.fft.irfft(spec, n)
    return x / (np.abs(x).max() + 1e-9)


def slow(n, rng, rate=0.15, lo=0.0, hi=1.0):
    """a slowly wandering value between lo and hi (for gusts, sweeps)"""
    k = max(4, int(n / RATE * rate * 4) + 4)
    pts = rng.uniform(0, 1, k)
    v = np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)
    sm = int(RATE / max(rate, 0.01) / 6)
    if sm > 1:                                             # a running average (one pass, not a huge convolution)
        p = np.concatenate([v[-sm:], v, v[:sm]])
        c = np.cumsum(np.concatenate([[0.0], p]))
        v = ((c[sm:] - c[:-sm]) / sm)[sm // 2: sm // 2 + n]
    v = (v - v.min()) / (v.max() - v.min() + 1e-9)
    return lo + (hi - lo) * v


def loop(x, f=RATE):
    """crossfade the tail into the head so it loops without a click"""
    head, tail = x[:f].copy(), x[-f:]
    r = np.linspace(0, 1, f)
    x = x[:-f].copy()
    x[:f] = head * r + tail * (1 - r)
    return x


def env(n, a, d):
    """attack a, decay d (fractions of n), smooth"""
    t = np.linspace(0, 1, n)
    return np.clip(np.minimum(t / max(a, 1e-4), (1 - t) / max(d, 1e-4)), 0, 1) ** 1.5


def grains(n, rng, per_s, lo, hi):
    """fine crackle: sparse tiny clicks, band-limited"""
    x = np.zeros(n)
    k = rng.integers(0, n, int(n / RATE * per_s))
    x[k] = rng.uniform(-1, 1, len(k))
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / RATE)
    spec *= (f > lo) & (f < hi)
    x = np.fft.irfft(spec, n)
    return x / (np.abs(x).max() + 1e-9)


def whistle(n, rng, f0, dur, start, breath, dyad=False):
    """wind through a gap: a sine that drifts in pitch, wavers, breathes, swells and fades"""
    out = np.zeros(n)
    m = int(dur * RATE)
    s0 = int(start * RATE)
    t = np.arange(m) / RATE
    glide = 1 + rng.uniform(-0.06, 0.06) * np.sin(np.pi * t / dur) + rng.uniform(-0.03, 0.03) * t / dur
    vib = 1 + 0.004 * np.sin(2 * np.pi * rng.uniform(3.5, 6) * t)
    freqs = [f0] + ([f0 * 1.059] if dyad else [])                  # a semitone apart beats eerily
    sig = np.zeros(m)
    for f in freqs:
        ph = 2 * np.pi * np.cumsum(f * glide * vib) / RATE
        sig += np.sin(ph) + 0.12 * np.sin(2 * ph)
    b = breath[(s0 + np.arange(m)) % len(breath)]
    sig *= (0.65 + 0.35 * b) * env(m, 0.35, 0.45)
    idx = (s0 + np.arange(m)) % n                                  # wraps round the loop
    out[idx] += sig / len(freqs)
    return out


def wind_bed(seconds, seed, rumble=1.0, hiss=1.0, crackle=1.0, whistles=3, whistle_hi=1300, drone=0.0, rattle=0.0):
    rng = np.random.default_rng(seed)
    n = RATE * seconds
    gust = slow(n, rng, 0.12, 0.25, 1.0)                           # the wind rising and falling
    x = band(n, 25, 180, rng) * rumble * (0.5 + 0.5 * gust)
    lo_hiss, hi_hiss = band(n, 300, 900, rng), band(n, 900, 2600, rng)
    mixk = slow(n, rng, 0.2)                                       # the hiss's colour sweeps as it gusts
    x += hiss * 0.55 * (lo_hiss * (1 - mixk) + hi_hiss * mixk) * gust ** 1.5
    x += crackle * 0.12 * grains(n, rng, 120, 1500, 6000) * gust
    breath = band(n, 2, 40, rng)
    for _ in range(whistles):
        dur = rng.uniform(2.5, 6.5)
        x += 0.22 * whistle(n, rng, rng.uniform(whistle_hi * 0.45, whistle_hi), dur, rng.uniform(0, seconds),
                            breath, dyad=rng.random() < 0.4)
    if drone:                                                     # two low sines, slightly apart: a slow throb
        t = np.arange(n) / RATE
        f = 55.0 * round(seconds * 55.0) / (seconds * 55.0)
        x += drone * 0.25 * (np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * (f + 1 / seconds * 23) * t)) * \
            slow(n, rng, 0.05, 0.4, 1.0)
    if rattle:                                                    # tin rattling somewhere when a gust hits
        for s in rng.uniform(0, seconds - 1, int(seconds * 0.4)):
            m = int(RATE * rng.uniform(0.15, 0.4))
            i0 = int(s * RATE)
            burst = band(m, 2000, 5000, rng) * (np.abs(np.sin(np.arange(m) / RATE * 2 * np.pi * rng.uniform(15, 30))))
            x[i0:i0 + m] += rattle * 0.25 * burst * env(m, 0.05, 0.7) * gust[i0]
    return loop(x)


def beds():
    """ambient loops, one per kind of place"""
    S = 20
    return {
        "amb_wind": wind_bed(S, 1, whistles=3),
        "amb_cold": wind_bed(S, 2, rumble=0.7, hiss=1.3, whistles=6, whistle_hi=1700),
        "amb_forest": wind_bed(S, 3, rumble=0.8, hiss=0.8, crackle=2.0, whistles=2, whistle_hi=1000),
        "amb_jungle": wind_bed(S, 4, rumble=0.6, hiss=1.0, crackle=2.5, whistles=1, drone=0.3),
        "amb_water": wind_bed(S, 5, rumble=1.2, hiss=0.6, crackle=0.4, whistles=1),
        "amb_lava": wind_bed(S, 6, rumble=1.6, hiss=0.5, crackle=1.5, whistles=1, drone=0.6),
        "amb_fungal": wind_bed(S, 7, rumble=0.6, hiss=0.5, whistles=2, whistle_hi=700, drone=0.8),
        "amb_crystal": wind_bed(S, 8, rumble=0.5, hiss=0.7, whistles=5, whistle_hi=2000),
        "amb_town": wind_bed(S, 9, rumble=0.8, hiss=0.9, whistles=4, whistle_hi=1100, rattle=1.0),
        "amb_night": wind_bed(S, 10, rumble=0.5, hiss=0.4, crackle=0.6, whistles=2, whistle_hi=800, drone=0.7),
    }


def sounds():
    """effects: foley, not beeps"""
    rng = np.random.default_rng(11)
    S = {}
    n = lambda s: int(s * RATE)

    def creak(dur, f0, f1, q=40):
        m = n(dur)
        sweep = np.linspace(f0, f1, m)
        x = np.zeros(m)                                        # a resonant band that slides: wood bending
        for k in range(0, m, 512):
            seg = band(min(512, m - k) + 512, sweep[k] - q, sweep[k] + q, rng)[:min(512, m - k)]
            x[k:k + len(seg)] = seg
        return x * env(m, 0.2, 0.3) * (0.6 + 0.4 * np.abs(np.sin(np.arange(m) / RATE * 2 * np.pi * 18)))

    def thud(dur, lo=30, hi=160):
        m = n(dur)
        return band(m, lo, hi, rng) * np.exp(-np.arange(m) / (m / 5))

    def rustle(dur, per_s=60, lo=1500, hi=6000):
        m = n(dur)
        return grains(m, rng, per_s, lo, hi) * env(m, 0.1, 0.4) * 0.8 + band(m, 2000, 7000, rng) * 0.15 * env(m, 0.2, 0.5)

    def cat(*parts, gap=0.0):
        out = []
        for p in parts:
            out += [p, np.zeros(n(gap))]
        return np.concatenate(out)

    S["open_wood"] = cat(creak(0.4, 520, 360), thud(0.18) * 0.8)
    S["open_metal"] = cat(thud(0.22, 40, 220), band(n(0.35), 1500, 3500, rng) * env(n(0.35), 0.1, 0.6) * 0.35)
    S["rummage"] = rustle(0.8)
    S["found"] = rustle(0.25, 90) * 0.7
    S["empty"] = rustle(0.2, 30, 800, 3000) * 0.5
    S["take"] = rustle(0.12, 120) * 0.6
    S["eat"] = cat(*[band(n(0.07), 900, 4000, rng) * np.exp(-np.arange(n(0.07)) / 300) for _ in range(3)], gap=0.1)
    S["drink"] = cat(*[band(n(0.12), 150, 500, rng) * env(n(0.12), 0.3, 0.6) for _ in range(3)], gap=0.06)
    S["heal"] = band(n(0.3), 2000, 7000, rng) * env(n(0.3), 0.05, 0.8)
    S["equip"] = band(n(0.3), 2500, 6000, rng) * env(n(0.3), 0.05, 0.9) * 0.6
    S["hit"] = thud(0.15, 60, 400)
    S["hurt"] = cat(thud(0.2, 40, 200), band(n(0.15), 300, 900, rng) * env(n(0.15), 0.1, 0.8) * 0.4)
    S["kill"] = cat(thud(0.3, 30, 150), wind_bed(3, 21, whistles=0)[:n(1.2)] * env(n(1.2), 0.3, 0.6) * 0.5)
    S["level"] = wind_bed(4, 22, rumble=0.3, hiss=0.3, whistles=1, whistle_hi=900)[:n(2.5)] * env(n(2.5), 0.3, 0.5)
    # title card: the wind rising, and a high, wavering whistle with a second note beating against it
    m = n(3.0)
    br = band(m, 2, 40, rng)
    S["sting"] = (band(m, 200, 2000, rng) * env(m, 0.4, 0.5) * 0.6 + band(m, 25, 150, rng) * env(m, 0.3, 0.6) * 0.6 +
                  whistle(m, rng, 1100, 2.6, 0.2, br, dyad=True) * 0.5)
    return S
