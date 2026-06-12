#include "fft.h"
#include "window.h"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <vector>

using namespace sound_viz;

int main() {
    const size_t n = 1024;
    const double sample_rate = 44100.0;
    const double freq = 1000.0;
    const double pi = 3.14159265358979323846;

    std::vector<float> signal(n);
    for (size_t i = 0; i < n; ++i) {
        signal[i] = static_cast<float>(std::sin(2.0 * pi * freq * static_cast<double>(i) / sample_rate));
    }

    std::vector<float> window(n);
    hann_window(window.data(), n);

    std::vector<float> windowed(n);
    apply_window(signal.data(), window.data(), windowed.data(), n);

    std::vector<float> spectrum(n / 2 + 1);
    real_fft_magnitude(windowed.data(), n, spectrum.data());

    size_t peak_bin = 0;
    float peak_val = 0.0f;
    for (size_t i = 0; i < spectrum.size(); ++i) {
        if (spectrum[i] > peak_val) {
            peak_val = spectrum[i];
            peak_bin = i;
        }
    }

    size_t expected_bin = static_cast<size_t>(std::lround(freq * static_cast<double>(n) / sample_rate));
    long diff = static_cast<long>(peak_bin) - static_cast<long>(expected_bin);

    assert(spectrum.size() == n / 2 + 1);
    assert(peak_val > 0.0f);
    assert(diff >= -1 && diff <= 1);

    printf("fft_test: all tests passed (peak_bin=%zu expected=%zu)\n", peak_bin, expected_bin);
    return 0;
}
