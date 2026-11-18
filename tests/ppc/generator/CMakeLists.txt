# SPDX-License-Identifier: GPL-3.0-only
cmake_minimum_required(VERSION 3.25)
project(mw3_ppc_generator LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(rexglue 0.11 REQUIRED CONFIG)
if(NOT DEFINED MW3_SDK_SOURCE)
  message(FATAL_ERROR "Missing verified SDK source")
endif()
set(template_output "${CMAKE_BINARY_DIR}/templates")
execute_process(COMMAND "${CMAKE_COMMAND}"
  "-DTEMPLATE_SOURCE_DIR=${MW3_SDK_SOURCE}/resources/templates"
  "-DTEMPLATE_OUTPUT_DIR=${template_output}"
  -P "${MW3_SDK_SOURCE}/cmake/embed_templates.cmake" COMMAND_ERROR_IS_FATAL ANY)
# Compile pinned translator sources unchanged, without rebuilding the runtime
# or embedding kernel objects. This small standalone target has no SDK fork.
file(GLOB translator CONFIGURE_DEPENDS
  "${MW3_SDK_SOURCE}/src/codegen/*.cpp"
  "${MW3_SDK_SOURCE}/src/codegen/builder/*.cpp"
  "${MW3_SDK_SOURCE}/src/codegen/ppc/*.cpp")
add_executable(ppc-generator adapter.cpp ${translator}
  "${MW3_SDK_SOURCE}/src/codegen/ppc/ppc_dis_access.c"
  "${MW3_SDK_SOURCE}/thirdparty/disasm/disasm.c"
  "${MW3_SDK_SOURCE}/thirdparty/xxHash/xxhash.c")
target_include_directories(ppc-generator PRIVATE "${MW3_SDK_SOURCE}/src"
  "${MW3_SDK_SOURCE}/src/codegen" "${template_output}"
  "${MW3_SDK_SOURCE}/thirdparty/disasm"
  "${MW3_SDK_SOURCE}/thirdparty/xxHash"
  "${MW3_SDK_SOURCE}/thirdparty/tomlplusplus/include"
  "${MW3_SDK_SOURCE}/thirdparty/inja/single_include"
  "${MW3_SDK_SOURCE}/thirdparty/inja/third_party/include")
target_link_libraries(ppc-generator PRIVATE rex::sdk)
rexglue_apply_target_settings(ppc-generator)
rexglue_configure_target(ppc-generator)
