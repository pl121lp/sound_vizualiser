#include "sound_viz/engine.h"
#include "ring_buffer.h"
#include "window.h"
#include "fft.h"
#include "dsp_features.h"

#include <vector>

struct EngineImpl {
    EngineConfig config;
    sound_viz::RingBuffer ring_buffer;
    std::vector<float> waveform_out;
    std::vector<float> window_coeffs;
    std::vector<float> windowed_buf;
    std::vector<float> spectrum_out;
    uint64_t frame_counter = 0;
    uint32_t last_channels = 1;

    explicit EngineImpl(EngineConfig cfg)
        : config(cfg),
          ring_buffer(cfg.window_size),
          waveform_out(cfg.window_size, 0.0f),
          window_coeffs(cfg.window_size, 0.0f),
          windowed_buf(cfg.window_size, 0.0f),
          spectrum_out(cfg.window_size / 2 + 1, 0.0f) {
        switch (config.fft_window_type) {
            case WINDOW_HAMMING:
                sound_viz::hamming_window(window_coeffs.data(), window_coeffs.size());
                break;
            case WINDOW_HANN:
            default:
                sound_viz::hann_window(window_coeffs.data(), window_coeffs.size());
                break;
        }
    }
};

extern "C" {

EngineHandle create_engine(EngineConfig config) {
    return new EngineImpl(config);
}

void push_samples(EngineHandle engine, const float* samples, uint32_t n_frames, uint32_t n_channels) {
    EngineImpl* impl = engine;
    impl->last_channels = n_channels;

    if (n_channels == 0) {
        return;
    }

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

    sound_viz::apply_window(impl->waveform_out.data(), impl->window_coeffs.data(),
                             impl->windowed_buf.data(), impl->windowed_buf.size());
    sound_viz::real_fft_magnitude(impl->windowed_buf.data(), impl->windowed_buf.size(),
                                   impl->spectrum_out.data());

    FeatureFrame frame{};
    frame.frame_index = impl->frame_counter++;
    frame.sample_rate = impl->config.sample_rate;
    frame.channels = impl->last_channels;
    frame.waveform = impl->waveform_out.data();
    frame.waveform_len = static_cast<uint32_t>(impl->waveform_out.size());
    frame.spectrum = impl->spectrum_out.data();
    frame.spectrum_len = static_cast<uint32_t>(impl->spectrum_out.size());

    frame.rms = sound_viz::compute_rms(impl->waveform_out.data(), impl->waveform_out.size());
    frame.zero_crossing_rate = sound_viz::compute_zero_crossing_rate(
        impl->waveform_out.data(), impl->waveform_out.size());
    frame.peak = sound_viz::compute_peak(impl->waveform_out.data(), impl->waveform_out.size());

    sound_viz::BandEnergy band_energy = sound_viz::compute_band_energy(
        impl->spectrum_out.data(), impl->spectrum_out.size(),
        impl->config.sample_rate, impl->config.window_size,
        impl->config.band_split_low_hz, impl->config.band_split_high_hz);
    frame.band_energy_low = band_energy.low;
    frame.band_energy_mid = band_energy.mid;
    frame.band_energy_high = band_energy.high;

    frame.spectral_centroid = sound_viz::compute_spectral_centroid(
        impl->spectrum_out.data(), impl->spectrum_out.size(),
        impl->config.sample_rate, impl->config.window_size);

    return frame;
}

void destroy_engine(EngineHandle engine) {
    delete engine;
}

}
