#pragma once

#include <cstddef>
#include <cstdint>

namespace sound_viz {

// Root-mean-square of `samples[0..n)`.
float compute_rms(const float* samples, size_t n);

// Fraction of adjacent-sample sign changes in `samples[0..n)`, in [0, 1].
// Returns 0 for n < 2.
float compute_zero_crossing_rate(const float* samples, size_t n);

// Maximum absolute value in `samples[0..n)`. Returns 0 for n == 0.
float compute_peak(const float* samples, size_t n);

struct BandEnergy {
    float low;
    float mid;
    float high;
};

// Sums squared magnitudes from `spectrum` (spectrum_len == window_size/2 + 1)
// into low/mid/high bands, split at 250 Hz and 4000 Hz. Bin i corresponds to
// frequency i * sample_rate / window_size.
BandEnergy compute_band_energy(const float* spectrum, size_t spectrum_len,
                                uint32_t sample_rate, uint32_t window_size);

// Magnitude-weighted mean frequency of `spectrum`. Returns 0 if the spectrum
// has zero total energy.
float compute_spectral_centroid(const float* spectrum, size_t spectrum_len,
                                  uint32_t sample_rate, uint32_t window_size);

} // namespace sound_viz
