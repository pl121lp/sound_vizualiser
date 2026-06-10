* Please work with me to improve this spec and iron out any issues or missing information before we build this system
- determine what features to focus on first, iterative : simple (PoC) to more advanced
- architecture and implementation details (with cross-platform considerations)

# Sound Visualizer

The system visualizes audio data in real-time using ... 

Consider a C++ processing engine but visualization using ?

## Sub components

TBD

## What to visualize

Characteristics to be considered visualized accross multiple dimensions
    - Time-domain (waveform)
        - amplitude (eg color effect when hitting specifci threshold)
        - RMS
        - zero corssing rate (noisiness indicator)
    - Frequency domain (from FFT)
        - Magnitude spectrum (FFT bins) (Shows frequency content at a moment)
        - Spectrogram (time + frequency) (How frequencies evolve over time)
        - Band energy (low/mid/high)   (Simplified EQ-style visualization)
    - More complex analysis
        - bpm detection
        - stereo specific characteristics

Considerations:
    - Scrolling vs static window
    - Vertical bars representing frequency bins (number of bins)
    - color gradients selection
    - Circular / radial visualizers (eg. Map frequency bins around a circle)
    - particle systems (for dynamic effects)

## Parameters

- Window size (WxH)
- Update rate (Hz)
- Audio input source (streamed from file)
- Audio sample rate (infer from file)
- Audio channels (infer from file)
- 

## Interactive controls

- rate (hz)
- buttons to select what to visualize (or combinations)

## Real-time considerations
- Buffering
    - Process chunks (e.g., 256–2048 samples)
    - Use ring buffers for smooth scrolling

- Latency vs resolution
    - Smaller buffers → faster updates, noisier
    - Larger buffers → smoother, more lag
    
- Windowing (for FFT)
    - Hann or Hamming

- Smoothing

