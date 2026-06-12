import os

import numpy as np
import soundfile as sf

SAMPLE_RATE = 44100
DURATION_S = 3.0
FREQUENCY_HZ = 440.0

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "test_tone.wav")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    t = np.arange(int(SAMPLE_RATE * DURATION_S)) / SAMPLE_RATE
    waveform = (0.5 * np.sin(2 * np.pi * FREQUENCY_HZ * t)).astype(np.float32)

    sf.write(OUTPUT_PATH, waveform, SAMPLE_RATE)
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
