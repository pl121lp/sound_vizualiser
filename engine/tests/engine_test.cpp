#include "sound_viz/engine.h"

#include <cassert>
#include <cmath>
#include <cstdio>

int main() {
    EngineConfig config{};
    config.window_size = 4;
    config.sample_rate = 44100;
    config.update_rate_hz = 0.0f;
    config.fft_window_type = WINDOW_HANN;
    config.band_split_low_hz = 250.0f;
    config.band_split_high_hz = 4000.0f;

    EngineHandle engine = create_engine(config);

    // First chunk: fewer samples than window_size -> zero-padded front.
    float chunk1[] = {1.0f, 2.0f};
    push_samples(engine, chunk1, 2, 1);

    FeatureFrame frame1 = get_latest_features(engine);
    assert(frame1.sample_rate == 44100);
    assert(frame1.channels == 1);
    assert(frame1.waveform_len == 4);
    assert(frame1.waveform[0] == 0.0f);
    assert(frame1.waveform[1] == 0.0f);
    assert(frame1.waveform[2] == 1.0f);
    assert(frame1.waveform[3] == 2.0f);
    assert(frame1.spectrum != nullptr);
    assert(frame1.spectrum_len == 3);
    assert(std::abs(frame1.rms - std::sqrt(1.25f)) < 1e-5f);
    assert(frame1.peak == 2.0f);
    assert(frame1.zero_crossing_rate == 0.0f);
    assert(frame1.frame_index == 0);

    // Second chunk: fills the window exactly.
    float chunk2[] = {3.0f, 4.0f, 5.0f, 6.0f};
    push_samples(engine, chunk2, 4, 1);

    FeatureFrame frame2 = get_latest_features(engine);
    assert(frame2.waveform[0] == 3.0f);
    assert(frame2.waveform[1] == 4.0f);
    assert(frame2.waveform[2] == 5.0f);
    assert(frame2.waveform[3] == 6.0f);
    assert(frame2.spectrum != nullptr);
    assert(frame2.spectrum_len == 3);
    assert(frame2.frame_index == 1);

    // Stereo chunk: mixed down to mono by averaging channels.
    float stereo[] = {2.0f, 4.0f}; // one frame, 2 channels -> mono 3.0
    push_samples(engine, stereo, 1, 2);

    FeatureFrame frame3 = get_latest_features(engine);
    assert(frame3.channels == 2);
    assert(frame3.waveform[3] == 3.0f);

    destroy_engine(engine);

    // Hamming window + custom band split configuration.
    EngineConfig hamming_config{};
    hamming_config.window_size = 16;
    hamming_config.sample_rate = 44100;
    hamming_config.update_rate_hz = 30.0f;
    hamming_config.fft_window_type = WINDOW_HAMMING;
    hamming_config.band_split_low_hz = 500.0f;
    hamming_config.band_split_high_hz = 2000.0f;

    EngineHandle hamming_engine = create_engine(hamming_config);

    float samples[16];
    for (int i = 0; i < 16; ++i) {
        samples[i] = static_cast<float>(i % 4) - 1.5f; // simple non-zero signal
    }
    push_samples(hamming_engine, samples, 16, 1);

    FeatureFrame hamming_frame = get_latest_features(hamming_engine);
    assert(hamming_frame.waveform_len == 16);
    assert(hamming_frame.spectrum_len == 9);
    assert(!std::isnan(hamming_frame.rms));
    assert(!std::isnan(hamming_frame.spectral_centroid));
    assert(hamming_frame.rms > 0.0f);

    destroy_engine(hamming_engine);

    printf("engine_test: all tests passed\n");
    return 0;
}
