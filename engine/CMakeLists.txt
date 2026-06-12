cmake_minimum_required(VERSION 3.15)
project(sound_viz_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(sound_viz_engine STATIC
    src/ring_buffer.cpp
    src/window.cpp
    src/fft.cpp
    src/engine.cpp
)
set_target_properties(sound_viz_engine PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(sound_viz_engine PUBLIC include)
target_include_directories(sound_viz_engine PRIVATE src third_party/pocketfft)

enable_testing()

add_executable(ring_buffer_test tests/ring_buffer_test.cpp)
target_include_directories(ring_buffer_test PRIVATE src)
target_link_libraries(ring_buffer_test PRIVATE sound_viz_engine)
add_test(NAME ring_buffer_test COMMAND ring_buffer_test)

add_executable(window_test tests/window_test.cpp)
target_include_directories(window_test PRIVATE src)
target_link_libraries(window_test PRIVATE sound_viz_engine)
add_test(NAME window_test COMMAND window_test)

add_executable(fft_test tests/fft_test.cpp)
target_include_directories(fft_test PRIVATE src)
target_link_libraries(fft_test PRIVATE sound_viz_engine)
add_test(NAME fft_test COMMAND fft_test)

add_executable(engine_test tests/engine_test.cpp)
target_link_libraries(engine_test PRIVATE sound_viz_engine)
add_test(NAME engine_test COMMAND engine_test)

find_package(pybind11 CONFIG QUIET)
if(pybind11_FOUND)
    pybind11_add_module(sound_viz_py bindings/python_bindings.cpp)
    target_link_libraries(sound_viz_py PRIVATE sound_viz_engine)
else()
    message(WARNING "pybind11 not found - skipping sound_viz_py Python module. "
                     "Pass -Dpybind11_DIR=$(frontend/.venv/bin/python -m pybind11 --cmakedir) to enable it.")
endif()
