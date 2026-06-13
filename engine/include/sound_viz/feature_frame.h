#pragma once

#include <cstdint>

extern "C" {

typedef enum {
    WINDOW_HANN = 0,
    WINDOW_HAMMING = 1,
} FftWindowType;

typedef struct {
    uint32_t window_size;       // N, e.g. 1024 — size of the analysis window
    uint32_t sample_rate;       // from WAV header; echoed back in FeatureFrame
    float update_rate_hz;       // advisory; echoed back, not used by the engine
    FftWindowType fft_window_type; // Hann or Hamming window applied before FFT
    float band_split_low_hz;    // low/mid band energy split point (Hz)
    float band_split_high_hz;   // mid/high band energy split point (Hz)
} EngineConfig;

typedef struct {
    uint64_t frame_index;
    uint32_t sample_rate;
    uint32_t channels;

    // Time-domain
    const float* waveform;     // populated in 1a: latest N samples, mono
    uint32_t waveform_len;     // == window_size (N)
    float rms;                 // populated in 1c: RMS of waveform
    float zero_crossing_rate;  // populated in 1c: fraction of sign changes in waveform
    float peak;                // populated in 1c: max abs sample in waveform

    // Frequency-domain
    const float* spectrum;     // populated in 1b: N/2+1 magnitude bins
    uint32_t spectrum_len;     // == window_size/2 + 1
    float band_energy_low;     // populated in 1c: energy below 250 Hz
    float band_energy_mid;     // populated in 1c: energy in 250-4000 Hz
    float band_energy_high;    // populated in 1c: energy above 4000 Hz
    float spectral_centroid;   // populated in 1c: magnitude-weighted mean frequency
} FeatureFrame;

}
