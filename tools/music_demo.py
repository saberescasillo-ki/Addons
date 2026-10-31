"""Makes the two demo songs of the "Reproductor de Música" add-on.

They are short original melodies synthesized here (no samples), only so the
add-on works out of the box. Delete them from sources/music_player/canciones/
when you add your own songs.

    python3 tools/music_demo.py      # writes the .ogg files (needs numpy and ffmpeg)
"""
import os
import subprocess
import tempfile
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "sources", "music_player", "canciones")
RATE = 32000


def freq(note):
    """MIDI note number -> Hz."""
    return 440.0 * 2 ** ((note - 69) / 12)


def pluck(note, length, vol=0.3, bright=3.0):
    """Soft music-box / harp-like tone."""
    t = np.arange(int(length * RATE)) / RATE
    f = freq(note)
    tone = sum(np.sin(2 * np.pi * f * k * t) / k ** bright for k in (1, 2, 3, 4))
    env = np.exp(-t * 3.2) * np.minimum(1, t * 200)
    return tone * env * vol


def pad(note, length, vol=0.08):
    """Slow warm chord tone."""
    t = np.arange(int(length * RATE)) / RATE
    f = freq(note)
    tone = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 1.003 * t) + 0.2 * np.sin(4 * np.pi * f * t)
    env = np.minimum(1, t / 0.8) * np.minimum(1, (length - t) / 0.8)
    return tone * env * vol


def render(beat, chords, melody, arp=True):
    """chords: list of (notes, beats); melody: list of (note or None, beats)."""
    total = sum(b for _, b in chords) * beat
    left = np.zeros(int((total + 3) * RATE))
    right = np.zeros_like(left)

    def add(sig, start, pan=0.5):
        i = int(start * RATE)
        n = min(len(sig), len(left) - i)
        left[i:i + n] += sig[:n] * (1 - pan) * 2
        right[i:i + n] += sig[:n] * pan * 2

    pos = 0.0
    for notes, beats in chords:
        for n in notes:
            add(pad(n - 12, beats * beat + 0.6), pos, 0.35)
        if arp:
            seq = notes + notes[1:-1][::-1]
            for k in range(int(beats * 2)):
                add(pluck(seq[k % len(seq)], 1.2, 0.12, 2.5), pos + k * beat / 2, 0.7)
        pos += beats * beat
    pos = 0.0
    for note, beats in melody:
        if note is not None:
            add(pluck(note, beats * beat + 1.0, 0.28), pos, 0.45)
        pos += beats * beat

    # small echo for space
    d = int(0.33 * RATE)
    for ch in (left, right):
        ch[d:] += ch[:-d] * 0.25
    peak = max(np.abs(left).max(), np.abs(right).max())
    return np.stack([left, right], axis=1) / peak * 0.8


def save(name, data):
    os.makedirs(OUT, exist_ok=True)
    pcm = (data * 32767).astype("<i2")
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "a.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm.tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis", "-q:a", "3",
                        os.path.join(OUT, name)], check=True)
    print("wrote", name)


def meadow():
    """Calm major song: C - G - Am - F."""
    C, G, Am, F = [60, 64, 67], [59, 62, 67], [57, 60, 64], [57, 60, 65]
    chords = [(C, 4), (G, 4), (Am, 4), (F, 4)] * 7
    phrase_a = [(72, 1), (76, 1), (79, 2), (79, 1), (77, 1), (76, 2),
                (74, 1), (76, 1), (72, 2), (72, 2), (None, 2),
                (69, 1), (72, 1), (76, 2), (74, 2), (72, 2)]
    phrase_b = [(77, 1), (76, 1), (74, 2), (72, 2), (74, 2),
                (76, 1), (79, 1), (81, 2), (79, 4),
                (77, 2), (76, 2), (74, 1), (72, 1), (72, 4)]
    return render(0.5, chords, [(None, 8)] + phrase_a + phrase_b + phrase_a + phrase_b)


def night():
    """Slow minor song: Am - F - C - E."""
    Am, F, C, E = [57, 60, 64], [53, 57, 60], [55, 60, 64], [56, 59, 64]
    chords = [(Am, 4), (F, 4), (C, 4), (E, 4)] * 3
    melody = [(None, 4), (76, 2), (74, 1), (72, 1), (71, 4), (None, 4), (72, 2), (71, 1), (69, 1), (68, 4),
              (69, 2), (72, 2), (76, 4), (77, 2), (76, 2), (72, 4), (71, 2), (69, 2), (68, 2), (71, 2), (69, 8),
              (None, 4)]
    return render(0.62, chords, melody)


if __name__ == "__main__":
    save("pradera_tranquila.ogg", meadow())
    save("noche_estrellada.ogg", night())
