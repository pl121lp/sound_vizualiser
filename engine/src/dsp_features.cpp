#include "dsp_features.h"

#include <cmath>

namespace sound_viz {

float compute_rms(const float* samples, size_t n) {
    if (n == 0) {
        return 0.0f;
    }
    double sum_sq = 0.0;
    for (size_t i = 0; i < n; ++i) {
        double s = static_cast<double>(samples[i]);
        sum_sq += s * s;
    }
    return static_cast<float>(std::sqrt(sum_sq / static_cast<double>(n)));
}

float compute_zero_crossing_rate(const float* samples, size_t n) {
    if (n < 2) {
        return 0.0f;
    }
    size_t crossings = 0;
    for (size_t i = 1; i < n; ++i) {
        bool prev_neg = samples[i - 1] < 0.0f;
        bool curr_neg = samples[i] < 0.0f;
        if (prev_neg != curr_neg) {
            ++crossings;
        }
    }
    return static_cast<float>(crossings) / static_cast<float>(n - 1);
}

float compute_peak(const float* samples, size_t n) {
    float peak = 0.0f;
    for (size_t i = 0; i < n; ++i) {
        float a = std::fabs(samples[i]);
        if (a > peak) {
            peak = a;
        }
    }
    return peak;
}

BandEnergy compute_band_energy(const float* spectrum, size_t spectrum_len,
                                uint32_t sample_rate, uint32_t window_size,
                                float low_split_hz, float high_split_hz) {
    BandEnergy result{0.0f, 0.0f, 0.0f};
    for (size_t i = 0; i < spectrum_len; ++i) {
        float freq = static_cast<float>(i) * static_cast<float>(sample_rate) /
                      static_cast<float>(window_size);
        float energy = spectrum[i] * spectrum[i];
        if (freq < low_split_hz) {
            result.low += energy;
        } else if (freq < high_split_hz) {
            result.mid += energy;
        } else {
            result.high += energy;
        }
    }
    return result;
}

float compute_spectral_centroid(const float* spectrum, size_t spectrum_len,
                                  uint32_t sample_rate, uint32_t window_size) {
    double weighted_sum = 0.0;
    double total = 0.0;
    for (size_t i = 0; i < spectrum_len; ++i) {
        float freq = static_cast<float>(i) * static_cast<float>(sample_rate) /
                      static_cast<float>(window_size);
        double mag = static_cast<double>(spectrum[i]);
        weighted_sum += freq * mag;
        total += mag;
    }
    if (total <= 0.0) {
        return 0.0f;
    }
    return static_cast<float>(weighted_sum / total);
}

} // namespace sound_viz
