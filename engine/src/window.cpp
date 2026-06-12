#include "window.h"

#include <cmath>

namespace sound_viz {

void hann_window(float* out, size_t n) {
    if (n == 1) {
        out[0] = 1.0f;
        return;
    }
    const float two_pi = 6.283185307179586f;
    for (size_t i = 0; i < n; ++i) {
        out[i] = 0.5f * (1.0f - std::cos(two_pi * static_cast<float>(i) / static_cast<float>(n - 1)));
    }
}

void apply_window(const float* in, const float* window, float* out, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        out[i] = in[i] * window[i];
    }
}

} // namespace sound_viz
