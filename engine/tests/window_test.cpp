#include "window.h"

#include <cassert>
#include <cmath>
#include <cstdio>

using namespace sound_viz;

void test_hann_window_endpoints_and_peak() {
    float w[5];
    hann_window(w, 5);
    assert(std::abs(w[0] - 0.0f) < 1e-6f);
    assert(std::abs(w[4] - 0.0f) < 1e-6f);
    assert(std::abs(w[2] - 1.0f) < 1e-6f); // center sample
}

void test_apply_window() {
    float in[3] = {2.0f, 3.0f, 4.0f};
    float win[3] = {0.5f, 1.0f, 0.0f};
    float out[3];
    apply_window(in, win, out, 3);
    assert(out[0] == 1.0f);
    assert(out[1] == 3.0f);
    assert(out[2] == 0.0f);
}

int main() {
    test_hann_window_endpoints_and_peak();
    test_apply_window();
    printf("window_test: all tests passed\n");
    return 0;
}
