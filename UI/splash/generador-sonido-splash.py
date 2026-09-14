import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt
import subprocess, os

sr = 44100
duration = 5.5
t = np.arange(int(sr * duration)) / sr
rng = np.random.default_rng(42)

def lowpass(x, cutoff, fs=sr, order=4):
    sos = butter(order, cutoff, btype="low", fs=fs, output="sos")
    return sosfilt(sos, x)

# Base atmospheric rumble: filtered noise with slow amplitude movement
noise = rng.normal(0, 1, len(t))
rumble = lowpass(noise, 95)
rumble_env = (
    0.08
    + 0.38 * np.exp(-((t - 1.15) / 1.05) ** 2)
    + 0.48 * np.exp(-((t - 3.65) / 1.25) ** 2)
)
audio = rumble * rumble_env

def thunder_strike(start, length, strength):
    global audio
    n = int(length * sr)
    local_t = np.arange(n) / sr
    
    # Sharp electric crack
    crack = rng.normal(0, 1, n)
    crack = np.sign(crack) * np.sqrt(np.abs(crack))
    crack_env = np.exp(-local_t / 0.045)
    crack *= crack_env
    
    # Deep thunder body, delayed slightly
    body_noise = lowpass(rng.normal(0, 1, n), 120)
    body_env = (1 - np.exp(-local_t / 0.08)) * np.exp(-local_t / 1.65)
    body = body_noise * body_env
    
    # Several resonant low frequencies for cinematic impact
    freqs = [38, 52, 71, 93]
    tones = sum(
        np.sin(2 * np.pi * f * local_t + rng.uniform(0, 2*np.pi))
        for f in freqs
    ) / len(freqs)
    tone_env = np.exp(-local_t / 1.9) * (1 - np.exp(-local_t / 0.05))
    
    strike = strength * (0.65 * crack + 0.72 * body + 0.32 * tones * tone_env)
    i = int(start * sr)
    j = min(i + n, len(audio))
    audio[i:j] += strike[:j-i]

# Three distinct lightning hits, progressively larger.
thunder_strike(0.55, 2.2, 0.75)
thunder_strike(2.45, 2.5, 0.95)
thunder_strike(4.15, 1.35, 1.20)

# Add a few short high-frequency "branch" cracks around the main strikes.
for start, strength in [(0.58, .35), (2.48, .42), (4.18, .55)]:
    n = int(.16 * sr)
    x = rng.normal(0, 1, n)
    x = butter(3, 4500, btype="highpass", fs=sr, output="sos")
    # regenerate to avoid state issues
    crack = rng.normal(0, 1, n)
    crack = sosfilt(x, crack)
    env = np.exp(-np.arange(n)/sr / .035)
    i = int(start*sr)
    audio[i:i+n] += strength * crack * env

# Fade in/out and normalize.
fade = int(.08 * sr)
audio[:fade] *= np.linspace(0, 1, fade)
audio[-fade:] *= np.linspace(1, 0, fade)
audio /= np.max(np.abs(audio)) + 1e-9
audio *= 0.92

out_dir = os.path.dirname(os.path.abspath(__file__))
wav_path = os.path.join(out_dir, "thunder-sound-splash.wav")
mp3_path = os.path.join(out_dir, "sonido.mp3")
wavfile.write(wav_path, sr, (audio * 32767).astype(np.int16))

subprocess.run(
    ["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path, "-codec:a", "libmp3lame", "-b:a", "192k", mp3_path],
    check=True
)
os.remove(wav_path)

print(f"Creado: {mp3_path}")
