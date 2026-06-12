#pragma once

#include <cstddef>

namespace sound_viz {

// Computes the magnitude spectrum of a real input of size n (n even).
// Writes n/2 + 1 magnitude values into `out`.
void real_fft_magnitude(const float* in, size_t n, float* out);

} // namespace sound_viz
