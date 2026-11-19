# SPDX-License-Identifier: GPL-3.0-only
cmake_minimum_required(VERSION 3.25)
project(mw3_gpu_bootstrap LANGUAGES CXX)
if(NOT WIN32 OR NOT DEFINED MW3_SDK_SOURCE)
  message(FATAL_ERROR "This isolated diagnostic requires verified native Windows SDK/source")
endif()
# The pinned SDK headers require C++23; the maintained public core stays C++20.
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
find_package(rexglue 0.11 REQUIRED CONFIG)
add_executable(gpu-bootstrap probe.cpp)
target_include_directories(gpu-bootstrap PRIVATE "${MW3_SDK_SOURCE}/src"
  "${MW3_SDK_SOURCE}/thirdparty/dxc/include" "${MW3_SDK_SOURCE}/thirdparty/imgui")
# The provider embeds this base statically; its inline introspection is not a DLL export.
target_compile_definitions(gpu-bootstrap PRIVATE REX_GPU_XENOS_STATIC)
target_link_libraries(gpu-bootstrap PRIVATE rex::base dxgi d3d12 user32)
rexglue_apply_target_settings(gpu-bootstrap)
rexglue_link_host_allocator(gpu-bootstrap)
option(MW3_GPU_HOST_UBSAN "Instrument original host probe; SDK/driver remain native" OFF)
if(MW3_GPU_HOST_UBSAN)
  target_compile_options(gpu-bootstrap PRIVATE -fsanitize=undefined -fsanitize-trap=all -fno-sanitize=vptr)
  target_link_options(gpu-bootstrap PRIVATE -fsanitize=undefined -fsanitize-trap=all -fno-sanitize=vptr)
endif()
