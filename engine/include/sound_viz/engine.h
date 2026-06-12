#pragma once

#include "sound_viz/feature_frame.h"

extern "C" {

typedef struct EngineImpl* EngineHandle;

EngineHandle create_engine(EngineConfig config);
void push_samples(EngineHandle engine, const float* samples, uint32_t n_frames, uint32_t n_channels);
FeatureFrame get_latest_features(EngineHandle engine);
void destroy_engine(EngineHandle engine);

}
