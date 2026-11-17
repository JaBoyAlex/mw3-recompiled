cmake_minimum_required(VERSION 3.25)
project(mw3_image_probe LANGUAGES CXX)
if(WIN32)
  message(FATAL_ERROR "This probe currently uses the canonical Ubuntu/WSL toolchain")
endif()
add_executable(mw3-image-probe image_probe.cpp)
target_compile_features(mw3-image-probe PRIVATE cxx_std_20)
target_include_directories(mw3-image-probe PRIVATE "${MW3_CPU_SOURCE}/XenonUtils" "${MW3_CPU_SOURCE}/thirdparty/simde")
target_link_libraries(mw3-image-probe PRIVATE
  "${MW3_CPU_BUILD}/XenonUtils/libXenonUtils.a"
  "${MW3_CPU_BUILD}/thirdparty/disasm/libdisasm.a")
