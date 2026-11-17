cmake_minimum_required(VERSION 3.25)
project(mw3_ppc_smoke LANGUAGES CXX)
add_executable(ppc-smoke
  "${MW3_FIXTURES}/ppc_smoke.cpp"
  "${MW3_GENERATED}/arithmetic.cpp"
  "${MW3_GENERATED}/memory.cpp"
  "${MW3_GENERATED}/branch.cpp"
  "${MW3_GENERATED}/rotate.cpp")
target_compile_features(ppc-smoke PRIVATE cxx_std_20)
target_include_directories(ppc-smoke PRIVATE "${MW3_CPU_SOURCE}/XenonUtils" "${MW3_CPU_SOURCE}/thirdparty/simde")
target_compile_options(ppc-smoke PRIVATE -march=x86-64-v2 -fwrapv)
