#include "sound_viz/engine.h"
#include "ring_buffer.h"

#include <vector>

struct EngineImpl {
    EngineConfig config;
    sound_viz::RingBuffer ring_buffer;
    std::vector<float> waveform_out;
    uint64_t frame_counter = 0;
    uint32_t last_channels = 1;

    explicit EngineImpl(EngineConfig cfg)
        : config(cfg),
          ring_buffer(cfg.window_size),
          waveform_out(cfg.window_size, 0.0f) {}
};

extern "C" {

EngineHandle create_engine(EngineConfig config) {
    return new EngineImpl(config);
}

void push_samples(EngineHandle engine, const float* samples, uint32_t n_frames, uint32_t n_channels) {
    EngineImpl* impl = engine;
    impl->last_channels = n_channels;

    if (n_channels == 1) {
        impl->ring_buffer.push(samples, n_frames);
        return;
    }

    std::vector<float> mono(n_frames);
    for (uint32_t i = 0; i < n_frames; ++i) {
        float sum = 0.0f;
        for (uint32_t c = 0; c < n_channels; ++c) {
            sum += samples[i * n_channels + c];
        }
        mono[i] = sum / static_cast<float>(n_channels);
    }
    impl->ring_buffer.push(mono.data(), n_frames);
}

FeatureFrame get_latest_features(EngineHandle engine) {
    EngineImpl* impl = engine;
    impl->ring_buffer.copy_latest(impl->waveform_out.data());

    FeatureFrame frame{};
    frame.frame_index = impl->frame_counter++;
    frame.sample_rate = impl->config.sample_rate;
    frame.channels = impl->last_channels;
    frame.waveform = impl->waveform_out.data();
    frame.waveform_len = static_cast<uint32_t>(impl->waveform_out.size());
    return frame;
}

void destroy_engine(EngineHandle engine) {
    delete engine;
}

}
