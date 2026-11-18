# SPDX-License-Identifier: GPL-3.0-only
cmake_minimum_required(VERSION 3.25)
project(mw3_guarded_header_probe LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(rexglue 0.11 REQUIRED CONFIG)
foreach(required MW3_GENERATED_DIR MW3_GENERATED_PREFIX MW3_PRIVATE_TRAPS MW3_DATA_IMPORT_HEADER)
  if(NOT DEFINED ${required})
    message(FATAL_ERROR "Missing verified private input: ${required}")
  endif()
endforeach()
get_filename_component(MW3_REPO "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
include("${MW3_GENERATED_DIR}/sources.cmake")
add_library(guest OBJECT ${GENERATED_SOURCES})
target_link_libraries(guest PRIVATE rex::sdk)
target_include_directories(guest PRIVATE "${MW3_GENERATED_DIR}")
rexglue_apply_target_settings(guest)
rexglue_recomp_options(guest_options optimized)
target_compile_options(guest PRIVATE ${guest_options} -fwrapv -ffp-contract=off)
target_precompile_headers(guest PRIVATE "${MW3_GENERATED_DIR}/${MW3_GENERATED_PREFIX}_pch.h")
add_executable(mw3-header-probe header_probe.cpp "${MW3_PRIVATE_TRAPS}" "${MW3_REPO}/src/xex.cpp")
option(MW3_PROBE_SANITIZERS "Instrument the original host harness/parser, not generated guest objects" OFF)
if(MW3_PROBE_SANITIZERS)
  if(WIN32)
    # The SDK's mandatory allocator shim collides with Windows ASan's new/delete
    # imports. Preserve that failed experiment; don't force duplicate symbols
    # or replace just one side of the cross-DLL allocator ABI.
    set(host_sanitizers undefined)
    # The packaged standalone UBSan C++ runtime also requires static CRT while
    # this SDK requires dynamic CRT. Trap mode retains checks without linking
    # an incompatible runtime. Calibrate its failure exit independently.
    target_compile_options(mw3-header-probe PRIVATE -fsanitize-trap=all)
    target_link_options(mw3-header-probe PRIVATE -fsanitize-trap=all)
  else()
    set(host_sanitizers address,undefined)
  endif()
  target_compile_options(mw3-header-probe PRIVATE -fsanitize=${host_sanitizers} -fno-sanitize=vptr -fno-omit-frame-pointer)
  target_link_options(mw3-header-probe PRIVATE -fsanitize=${host_sanitizers} -fno-sanitize=vptr)
endif()
target_include_directories(mw3-header-probe PRIVATE "${MW3_GENERATED_DIR}" "${MW3_REPO}/include")
target_compile_definitions(mw3-header-probe PRIVATE
  MW3_GENERATED_INIT="${MW3_GENERATED_PREFIX}_init.h"
  MW3_DATA_IMPORT_HEADER="${MW3_DATA_IMPORT_HEADER}")
target_link_libraries(mw3-header-probe PRIVATE guest rex::sdk)
rexglue_apply_target_settings(mw3-header-probe)
rexglue_configure_target(mw3-header-probe)
