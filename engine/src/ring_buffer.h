#pragma once

#include <cstddef>
#include <vector>

namespace sound_viz {

class RingBuffer {
public:
    explicit RingBuffer(size_t capacity);

    // Appends `count` samples to the buffer, overwriting the oldest samples
    // once capacity is exceeded.
    void push(const float* samples, size_t count);

    // Writes the most recent capacity() samples into `out`, oldest first.
    // Zero-pads the front until capacity() samples have been pushed in total.
    void copy_latest(float* out) const;

    size_t capacity() const { return buffer_.size(); }

private:
    std::vector<float> buffer_;
    size_t write_pos_ = 0;
    size_t total_pushed_ = 0;
};

} // namespace sound_viz
