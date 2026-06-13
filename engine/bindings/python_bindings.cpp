#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include <cstring>
#include <string>

#include "sound_viz/engine.h"

namespace py = pybind11;

class PyEngine {
public:
    PyEngine(uint32_t window_size, uint32_t sample_rate,
             float update_rate_hz = 0.0f,
             const std::string& fft_window_type = "hann",
             float band_split_low_hz = 250.0f,
             float band_split_high_hz = 4000.0f) {
        EngineConfig config{};
        config.window_size = window_size;
        config.sample_rate = sample_rate;
        config.update_rate_hz = update_rate_hz;
        config.band_split_low_hz = band_split_low_hz;
        config.band_split_high_hz = band_split_high_hz;

        if (fft_window_type == "hann") {
            config.fft_window_type = WINDOW_HANN;
        } else if (fft_window_type == "hamming") {
            config.fft_window_type = WINDOW_HAMMING;
        } else {
            throw py::value_error("fft_window_type must be 'hann' or 'hamming'");
        }

        handle_ = create_engine(config);
    }

    ~PyEngine() {
        destroy_engine(handle_);
    }

    void push_samples(py::array_t<float, py::array::c_style | py::array::forcecast> samples,
                       uint32_t n_channels) {
        if (n_channels == 0) {
            throw py::value_error("n_channels must be greater than zero");
        }
        auto buf = samples.request();
        uint32_t n_frames = static_cast<uint32_t>(buf.size) / n_channels;
        ::push_samples(handle_, static_cast<const float*>(buf.ptr), n_frames, n_channels);
    }

    py::dict get_latest_features() {
        FeatureFrame frame = ::get_latest_features(handle_);

        py::array_t<float> waveform(frame.waveform_len);
        std::memcpy(waveform.mutable_data(), frame.waveform, frame.waveform_len * sizeof(float));

        py::array_t<float> spectrum(frame.spectrum_len);
        std::memcpy(spectrum.mutable_data(), frame.spectrum, frame.spectrum_len * sizeof(float));

        py::dict result;
        result["frame_index"] = frame.frame_index;
        result["sample_rate"] = frame.sample_rate;
        result["channels"] = frame.channels;
        result["waveform"] = waveform;
        result["spectrum"] = spectrum;
        result["rms"] = frame.rms;
        result["zero_crossing_rate"] = frame.zero_crossing_rate;
        result["peak"] = frame.peak;
        result["band_energy_low"] = frame.band_energy_low;
        result["band_energy_mid"] = frame.band_energy_mid;
        result["band_energy_high"] = frame.band_energy_high;
        result["spectral_centroid"] = frame.spectral_centroid;
        return result;
    }

private:
    EngineHandle handle_;
};

PYBIND11_MODULE(sound_viz_py, m) {
    py::class_<PyEngine>(m, "Engine")
        .def(py::init<uint32_t, uint32_t, float, const std::string&, float, float>(),
             py::arg("window_size"), py::arg("sample_rate"),
             py::arg("update_rate_hz") = 0.0f,
             py::arg("fft_window_type") = "hann",
             py::arg("band_split_low_hz") = 250.0f,
             py::arg("band_split_high_hz") = 4000.0f)
        .def("push_samples", &PyEngine::push_samples, py::arg("samples"), py::arg("n_channels") = 1)
        .def("get_latest_features", &PyEngine::get_latest_features);
}
