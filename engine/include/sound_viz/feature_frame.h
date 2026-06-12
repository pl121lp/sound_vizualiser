#pragma once

#include <cstdint>

extern "C" {

typedef struct {
    uint32_t window_size;   // N, e.g. 1024 — size of the analysis window
    uint32_t sample_rate;   // from WAV header; echoed back in FeatureFrame
} EngineConfig;

typedef struct {
    uint64_t frame_index;
    uint32_t sample_rate;
    uint32_t channels;

    // Time-domain
    const float* waveform;     // populated in 1a: latest N samples, mono
    uint32_t waveform_len;     // == window_size (N)
    float rms;                 // 0 in 1a (added in 1c)
    float zero_crossing_rate;  // 0 in 1a (added in 1c)
    float peak;                // 0 in 1a (added in 1c)

    // Frequency-domain
    const float* spectrum;     // populated in 1b: N/2+1 magnitude bins
    uint32_t spectrum_len;     // == window_size/2 + 1
    float band_energy_low;     // 0 in 1a (added in 1c)
    float band_energy_mid;     // 0 in 1a (added in 1c)
    float band_energy_high;    // 0 in 1a (added in 1c)
    float spectral_centroid;   // 0 in 1a (added in 1c)
} FeatureFrame;

}
