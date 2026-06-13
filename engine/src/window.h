#pragma once

#include <cstddef>

namespace sound_viz {

// Fills `out` (size n) with Hann window coefficients.
void hann_window(float* out, size_t n);

// Fills `out` (size n) with Hamming window coefficients.
void hamming_window(float* out, size_t n);

// out[i] = in[i] * window[i], for i in [0, n)
void apply_window(const float* in, const float* window, float* out, size_t n);

} // namespace sound_viz
