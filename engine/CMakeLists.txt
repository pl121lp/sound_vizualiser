cmake_minimum_required(VERSION 3.15)
project(sound_viz_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(sound_viz_engine STATIC
    src/ring_buffer.cpp
    src/engine.cpp
)
target_include_directories(sound_viz_engine PUBLIC include)
target_include_directories(sound_viz_engine PRIVATE src)

enable_testing()

add_executable(ring_buffer_test tests/ring_buffer_test.cpp)
target_include_directories(ring_buffer_test PRIVATE src)
target_link_libraries(ring_buffer_test PRIVATE sound_viz_engine)
add_test(NAME ring_buffer_test COMMAND ring_buffer_test)

add_executable(engine_test tests/engine_test.cpp)
target_link_libraries(engine_test PRIVATE sound_viz_engine)
add_test(NAME engine_test COMMAND engine_test)
