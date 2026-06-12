#include "fft.h"
#include "pocketfft_hdronly.h"

#include <complex>
#include <vector>

namespace sound_viz {

void real_fft_magnitude(const float* in, size_t n, float* out) {
    pocketfft::shape_t shape{n};
    pocketfft::stride_t stride_in{sizeof(float)};
    pocketfft::stride_t stride_out{sizeof(std::complex<float>)};
    pocketfft::shape_t axes{0};

    std::vector<std::complex<float>> spectrum(n / 2 + 1);
    pocketfft::r2c(shape, stride_in, stride_out, axes, true, in, spectrum.data(), 1.0f);

    for (size_t i = 0; i < spectrum.size(); ++i) {
        out[i] = std::abs(spectrum[i]);
    }
}

} // namespace sound_viz
