#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include "fft.h"
#include "dsp_features.h"
#include "window.h"

#include <cmath>
#include <vector>

using namespace sound_viz;
using Catch::Approx;

namespace {

// Generates a Hann-windowed pure sine and its magnitude spectrum.
std::vector<float> sine_spectrum(double freq, double sample_rate, size_t n) {
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
    return spectrum;
}

} // namespace

TEST_CASE("compute_rms of an alternating +-1 signal is 1.0", "[features]") {
    float samples[] = {1.0f, -1.0f, 1.0f, -1.0f};
    REQUIRE(compute_rms(samples, 4) == Approx(1.0f));
}

TEST_CASE("compute_rms of silence is 0", "[features]") {
    float samples[] = {0.0f, 0.0f, 0.0f};
    REQUIRE(compute_rms(samples, 3) == Approx(0.0f));
}

TEST_CASE("compute_peak finds the maximum absolute value", "[features]") {
    float samples[] = {0.2f, -0.9f, 0.5f};
    REQUIRE(compute_peak(samples, 3) == Approx(0.9f));
}

TEST_CASE("compute_zero_crossing_rate counts sign changes", "[features]") {
    float samples[] = {1.0f, -1.0f, 1.0f, -1.0f, 1.0f};
    REQUIRE(compute_zero_crossing_rate(samples, 5) == Approx(1.0f));
}

TEST_CASE("compute_zero_crossing_rate of a constant signal is 0", "[features]") {
    float samples[] = {1.0f, 1.0f, 1.0f, 1.0f};
    REQUIRE(compute_zero_crossing_rate(samples, 4) == Approx(0.0f));
}

TEST_CASE("compute_spectral_centroid matches a pure tone's frequency", "[features]") {
    const size_t n = 1024;
    const double sample_rate = 44100.0;
    const double freq = 1000.0;

    std::vector<float> spectrum = sine_spectrum(freq, sample_rate, n);

    float centroid = compute_spectral_centroid(spectrum.data(), spectrum.size(),
                                                 static_cast<uint32_t>(sample_rate),
                                                 static_cast<uint32_t>(n));
    REQUIRE(centroid == Approx(static_cast<float>(freq)).margin(100.0f));
}

TEST_CASE("compute_spectral_centroid of silence is 0", "[features]") {
    const size_t spectrum_len = 513;
    std::vector<float> spectrum(spectrum_len, 0.0f);

    float centroid = compute_spectral_centroid(spectrum.data(), spectrum.size(), 44100, 1024);
    REQUIRE(centroid == Approx(0.0f));
}

TEST_CASE("compute_band_energy puts a 1kHz tone in the mid band", "[features]") {
    const size_t n = 1024;
    const double sample_rate = 44100.0;
    const double freq = 1000.0;

    std::vector<float> spectrum = sine_spectrum(freq, sample_rate, n);

    BandEnergy energy = compute_band_energy(spectrum.data(), spectrum.size(),
                                             static_cast<uint32_t>(sample_rate),
                                             static_cast<uint32_t>(n), 250.0f, 4000.0f);
    REQUIRE(energy.mid > energy.low);
    REQUIRE(energy.mid > energy.high);
}

TEST_CASE("compute_band_energy puts a 100Hz tone in the low band", "[features]") {
    const size_t n = 1024;
    const double sample_rate = 44100.0;
    const double freq = 100.0;

    std::vector<float> spectrum = sine_spectrum(freq, sample_rate, n);

    BandEnergy energy = compute_band_energy(spectrum.data(), spectrum.size(),
                                             static_cast<uint32_t>(sample_rate),
                                             static_cast<uint32_t>(n), 250.0f, 4000.0f);
    REQUIRE(energy.low > energy.mid);
    REQUIRE(energy.low > energy.high);
}

TEST_CASE("compute_band_energy respects custom split points", "[features]") {
    const size_t n = 1024;
    const double sample_rate = 44100.0;
    const double freq = 1000.0;

    std::vector<float> spectrum = sine_spectrum(freq, sample_rate, n);

    // With the default 250/4000 Hz split, 1 kHz falls in "mid". With a
    // 2000 Hz low/mid split, 1 kHz now falls in "low".
    BandEnergy energy = compute_band_energy(spectrum.data(), spectrum.size(),
                                             static_cast<uint32_t>(sample_rate),
                                             static_cast<uint32_t>(n), 2000.0f, 8000.0f);
    REQUIRE(energy.low > energy.mid);
    REQUIRE(energy.low > energy.high);
}
