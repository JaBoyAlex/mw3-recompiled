# SPDX-License-Identifier: GPL-3.0-only
cmake_minimum_required(VERSION 3.25)
project(mw3_thread_diagnostics LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(rexglue 0.11 REQUIRED CONFIG)
if(NOT DEFINED MW3_SDK_SOURCE)
  message(FATAL_ERROR "Missing verified SDK source")
endif()
set(CATCH_INSTALL_DOCS OFF CACHE BOOL "" FORCE)
set(CATCH_INSTALL_EXTRAS OFF CACHE BOOL "" FORCE)
add_subdirectory("${MW3_SDK_SOURCE}/thirdparty/catch2" "${CMAKE_BINARY_DIR}/catch2" EXCLUDE_FROM_ALL)
# These upstream tests exercise platform threads alongside original contracts.
# No SDK module/kernel object libraries are embedded in this executable.
add_executable(thread-platform-tests
  platform.cpp
  "${MW3_SDK_SOURCE}/tests/unit/base/thread_start_data_test.cpp"
  "${MW3_SDK_SOURCE}/tests/unit/base/thread_time_test.cpp"
  "${MW3_SDK_SOURCE}/tests/unit/base/thread_priority_test.cpp")
target_include_directories(thread-platform-tests PRIVATE
  "${MW3_SDK_SOURCE}/src" "${MW3_SDK_SOURCE}/tests" "${MW3_SDK_SOURCE}/tests/unit")
target_compile_definitions(thread-platform-tests PRIVATE REX_TEST_REAL_MODULES)
target_link_libraries(thread-platform-tests PRIVATE rex::sdk Catch2::Catch2WithMain)
rexglue_apply_target_settings(thread-platform-tests)
rexglue_configure_target(thread-platform-tests)
option(MW3_THREAD_SANITIZERS "Instrument test callbacks; SDK has its own receipt" OFF)
if(MW3_THREAD_SANITIZERS)
  if(WIN32)
    target_compile_options(thread-platform-tests PRIVATE -fsanitize=undefined -fsanitize-trap=all -fno-sanitize=vptr)
    target_link_options(thread-platform-tests PRIVATE -fsanitize=undefined -fsanitize-trap=all -fno-sanitize=vptr)
  else()
    target_compile_options(thread-platform-tests PRIVATE -fsanitize=address,undefined -fno-sanitize=vptr -fno-omit-frame-pointer)
    target_link_options(thread-platform-tests PRIVATE -fsanitize=address,undefined -fno-sanitize=vptr)
  endif()
endif()
