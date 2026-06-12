#include "ring_buffer.h"

namespace sound_viz {

RingBuffer::RingBuffer(size_t capacity) : buffer_(capacity, 0.0f) {}

void RingBuffer::push(const float* samples, size_t count) {
    size_t capacity = buffer_.size();
    for (size_t i = 0; i < count; ++i) {
        buffer_[write_pos_] = samples[i];
        write_pos_ = (write_pos_ + 1) % capacity;
    }
    total_pushed_ += count;
}

void RingBuffer::copy_latest(float* out) const {
    size_t capacity = buffer_.size();
    if (total_pushed_ >= capacity) {
        for (size_t i = 0; i < capacity; ++i) {
            out[i] = buffer_[(write_pos_ + i) % capacity];
        }
        return;
    }

    size_t pad = capacity - total_pushed_;
    for (size_t i = 0; i < pad; ++i) {
        out[i] = 0.0f;
    }
    for (size_t i = 0; i < total_pushed_; ++i) {
        out[pad + i] = buffer_[i];
    }
}

} // namespace sound_viz
