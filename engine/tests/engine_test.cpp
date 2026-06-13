#include "sound_viz/engine.h"

#include <cassert>
#include <cmath>
#include <cstdio>

int main() {
    EngineConfig config{};
    config.window_size = 4;
    config.sample_rate = 44100;

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

    printf("engine_test: all tests passed\n");
    return 0;
}
