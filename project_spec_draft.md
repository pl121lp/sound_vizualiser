

# Sound Visualizer

The system visualizes audio data in real-time using suitable visualization framework 

The visualizer should read and visualize a specified set of samples at a time.

Consider a portable C++ engine that does the analysis but visualization using a more suitable frontend.
The frontend can be something like python (or platform specific framework) initially.
By decoupling backend from frontend its easier to change out frontend later, as long as the interface is clean. 

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

## Potential configurable parameters

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


## Iterative development plan

TBD

