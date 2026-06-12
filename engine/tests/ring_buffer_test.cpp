#include "ring_buffer.h"

#include <cassert>
#include <cstdio>
#include <vector>

using sound_viz::RingBuffer;

void test_zero_padding_before_full() {
    RingBuffer rb(4);
    float samples[] = {1.0f, 2.0f};
    rb.push(samples, 2);

    std::vector<float> out(4);
    rb.copy_latest(out.data());

    assert(out[0] == 0.0f);
    assert(out[1] == 0.0f);
    assert(out[2] == 1.0f);
    assert(out[3] == 2.0f);
}

void test_wraps_when_over_capacity() {
    RingBuffer rb(4);
    float samples[] = {1.0f, 2.0f, 3.0f, 4.0f, 5.0f, 6.0f};
    rb.push(samples, 6);

    std::vector<float> out(4);
    rb.copy_latest(out.data());

    assert(out[0] == 3.0f);
    assert(out[1] == 4.0f);
    assert(out[2] == 5.0f);
    assert(out[3] == 6.0f);
}

int main() {
    test_zero_padding_before_full();
    test_wraps_when_over_capacity();
    printf("ring_buffer_test: all tests passed\n");
    return 0;
}
