"""The epic song of the hunt's final duel (an original piece, synthesised here).

D minor, 132 bpm, 32 bars (~58 s) that loop: war drums, a string ostinato,
low brass, a choir and a heroic brass theme that climbs in the last part.

    python3 tools/natura_pvp/music.py out.ogg   # renders and encodes (needs ffmpeg)
"""
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

SR = 44100
BPM = 132
BEAT = 60 / BPM
BAR = 4 * BEAT
BARS = 32
LENGTH = BARS * BAR
rng = np.random.default_rng(20261110)


def hz(note):
    return 440.0 * 2 ** ((note - 69) / 12)


def env(n, attack, release, sustain_curve=0.0):
    t = np.arange(n) / SR
    a = np.minimum(1, t / max(attack, 1e-4))
    r = np.minimum(1, (n / SR - t) / max(release, 1e-4))
    s = np.exp(-t * sustain_curve) if sustain_curve else 1
    return a * np.clip(r, 0, 1) * s


def tone(freq, dur, harmonics=12, bright=4.0, detune=(0.0,), vibrato=0.0, phase_rand=True):
    """Additive, band-limited saw-like tone (rolloff = a gentle low-pass)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    vib = 1 + vibrato * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / 0.4)
    for d in detune:
        f = freq * 2 ** (d / 1200)
        ph = np.cumsum(np.full(n, f) * vib) / SR * 2 * np.pi
        for k in range(1, harmonics + 1):
            if f * k > SR / 2.2:
                break
            amp = (1 / k) * np.exp(-(k - 1) / bright)
            off = rng.uniform(0, 2 * np.pi) if phase_rand else 0
            out += amp * np.sin(k * ph + off)
    return out / len(detune)


def add(buf, start, sig, gain=1.0):
    i = int(start * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def noise(n):
    return rng.uniform(-1, 1, n)


def lowpass(sig, cut):
    """Simple FFT low-pass."""
    spec = np.fft.rfft(sig)
    freqs = np.fft.rfftfreq(len(sig), 1 / SR)
    spec *= 1 / (1 + (freqs / cut) ** 4)
    return np.fft.irfft(spec, len(sig))


def highpass(sig, cut):
    spec = np.fft.rfft(sig)
    freqs = np.fft.rfftfreq(len(sig), 1 / SR)
    spec *= 1 / (1 + (cut / np.maximum(freqs, 1)) ** 4)
    return np.fft.irfft(spec, len(sig))


# ------------------------------------------------------------ instruments
def taiko(big=True):
    dur = 0.9 if big else 0.45
    n = int(dur * SR)
    t = np.arange(n) / SR
    f0, f1 = (95, 42) if big else (160, 80)
    f = f1 + (f0 - f1) * np.exp(-t * 18)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (5 if big else 9))
    hit = lowpass(noise(n), 1800) * np.exp(-t * 40) * 0.6
    return np.tanh((body + hit) * 1.6)


def snare():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    s = highpass(noise(n), 900) * np.exp(-t * 14) * 0.7
    s += np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) * 0.5
    return s


def crash():
    n = int(2.8 * SR)
    t = np.arange(n) / SR
    return highpass(noise(n), 4500) * np.exp(-t * 1.6) * 0.5


def string_note(note, dur):
    s = tone(hz(note), dur, harmonics=14, bright=3.5, detune=(-7, 0, 6))
    return s * env(len(s), 0.004, 0.03, 9)


def bass_note(note, dur):
    s = tone(hz(note), dur, harmonics=8, bright=2.5, detune=(-4, 4))
    return s * env(len(s), 0.01, 0.05, 2.5)


def brass_note(note, dur):
    s = tone(hz(note), dur, harmonics=16, bright=5.5, detune=(-9, 0, 8), vibrato=0.004)
    e = env(len(s), 0.07, 0.12)
    # the brass gets brighter as it opens
    swell = tone(hz(note), dur, harmonics=4, bright=1.5) * env(len(s), 0.03, 0.12)
    return (s * e + swell * 0.4) * 0.9


def choir_note(note, dur):
    s = tone(hz(note), dur, harmonics=6, bright=1.4, detune=(-12, -4, 5, 13), vibrato=0.006)
    return s * env(len(s), 0.5, 0.6)


# ------------------------------------------------------------ the score
D, E, F, G, A, Bb, C = 62, 64, 65, 67, 69, 70, 72  # D4 ... C5
# chord per bar (root in octave 2-3, triad tones)
PROG = [
    (38, [62, 65, 69]),  # Dm
    (34, [62, 65, 70]),  # Bb
    (41, [60, 65, 69]),  # F
    (36, [60, 64, 67]),  # C
    (38, [62, 65, 69]),  # Dm
    (34, [62, 65, 70]),  # Bb
    (43, [62, 67, 70]),  # Gm
    (33, [61, 64, 69]),  # A
]

# heroic theme: (midi, beats) per bar, 8 bars
THEME = [
    [(74, 1.5), (69, 0.5), (74, 1), (76, 1)],
    [(77, 2), (76, 1), (74, 1)],
    [(72, 1.5), (69, 0.5), (72, 1), (74, 1)],
    [(76, 3), (72, 1)],
    [(74, 1.5), (69, 0.5), (74, 1), (77, 1)],
    [(79, 2), (77, 1), (76, 1)],
    [(74, 1), (76, 1), (77, 1), (79, 1)],
    [(81, 3), (73, 1)],
]


def render():
    n = int(LENGTH * SR) + SR * 3
    drums = np.zeros(n)
    strings = np.zeros(n)
    low = np.zeros(n)
    lead = np.zeros(n)
    pad = np.zeros(n)
    big, small, sn, cr = taiko(True), taiko(False), snare(), crash()
    for bar in range(BARS):
        t0 = bar * BAR
        section = bar // 8  # 0 intro, 1 theme, 2 choir, 3 climax
        root, triad = PROG[bar % 8]
        # war drums
        for beat in (0, 1.5, 2, 3):
            add(drums, t0 + beat * BEAT, big, 0.9 if beat == 0 else 0.7)
        if section >= 1:
            for beat in (0.75, 2.75, 3.5):
                add(drums, t0 + beat * BEAT, small, 0.45)
            for beat in (1, 3):
                add(drums, t0 + beat * BEAT, sn, 0.35 if section < 3 else 0.5)
        if bar % 8 == 7:
            for k in range(8):
                add(drums, t0 + (2 + k * 0.25) * BEAT, small, 0.3 + k * 0.06)
        if bar % 8 == 0 and bar > 0:
            add(drums, t0, cr, 0.6)
        # string ostinato (16ths)
        pattern = [0, 0, 7, 0, 12, 0, 7, 0, 0, 0, 7, 0, 12, 7, 3 if bar % 8 in (0, 4) else 5, 7]
        for k, iv in enumerate(pattern):
            note = root + 24 + iv
            acc = 1.0 if k % 4 == 0 else 0.65
            add(strings, t0 + k * BEAT / 4, string_note(note, BEAT / 4 * 0.95), 0.22 * acc)
        # low brass / bass on 8ths
        for k in range(8):
            add(low, t0 + k * BEAT / 2, bass_note(root + (12 if k % 2 else 0), BEAT / 2 * 0.9), 0.32)
        # choir from the third section
        if section >= 2:
            for note in triad:
                add(pad, t0, choir_note(note, BAR * 1.02), 0.16)
            add(pad, t0, choir_note(triad[0] - 12, BAR * 1.02), 0.12)
        # the theme (an octave lower first, then high and doubled in the climax)
        if section >= 1:
            pos = t0
            for note, beats in THEME[bar % 8]:
                shift = -12 if section == 1 else 0
                dur = beats * BEAT
                add(lead, pos, brass_note(note + shift, dur * 0.97), 0.32)
                if section == 3:
                    add(lead, pos, brass_note(note + shift - 12, dur * 0.97), 0.2)
                pos += dur
        elif bar % 2 == 1:
            # intro: a low horn call
            add(lead, t0, brass_note(root + 24, BAR * 0.95), 0.18)
    mix = drums * 0.95 + strings + low + lead + pad
    # hall reverb: decaying noise as the impulse response
    ir_n = int(2.2 * SR)
    t = np.arange(ir_n) / SR
    ir = lowpass(noise(ir_n), 6000) * np.exp(-t * 2.6)
    ir[0] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    size = 1 << int(np.ceil(np.log2(len(mix) + ir_n)))
    wet = np.fft.irfft(np.fft.rfft(mix, size) * np.fft.rfft(ir, size), size)[: len(mix)]
    out = mix * 0.82 + wet * 0.35
    # loop: fold the reverb tail back into the start
    loop_n = int(LENGTH * SR)
    tail = out[loop_n:]
    out = out[:loop_n].copy()
    out[: len(tail)] += tail
    out = highpass(out, 30)
    out /= np.max(np.abs(out)) + 1e-9
    out = np.tanh(out * 1.4) / np.tanh(1.4)
    # tiny fade at the very ends (no click on loop)
    f = int(0.01 * SR)
    out[:f] *= np.linspace(0, 1, f)
    out[-f:] *= np.linspace(1, 0, f)
    return out * 0.92


def write_ogg(path):
    data = render()
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "epic.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((data * 32767).astype("<i2").tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis", "-q:a", "5", path], check=True)
    return LENGTH


if __name__ == "__main__":
    print(round(write_ogg(sys.argv[1] if len(sys.argv) > 1 else "epic.ogg"), 2), "s")
