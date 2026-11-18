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
add_executable(thread-kernel-tests kernel.cpp)
target_include_directories(thread-kernel-tests PRIVATE "${MW3_SDK_SOURCE}/src")
target_link_libraries(thread-kernel-tests PRIVATE rex::sdk Catch2::Catch2WithMain)
rexglue_apply_target_settings(thread-kernel-tests)
rexglue_configure_target(thread-kernel-tests)
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
# Combined orders expose interactions across both tranches while compiling
# Catch2 only once per fresh profile when --suite all is selected.
add_executable(thread-all-tests kernel.cpp platform.cpp
  "${MW3_SDK_SOURCE}/tests/unit/base/thread_start_data_test.cpp"
  "${MW3_SDK_SOURCE}/tests/unit/base/thread_time_test.cpp"
  "${MW3_SDK_SOURCE}/tests/unit/base/thread_priority_test.cpp")
target_include_directories(thread-all-tests PRIVATE
  "${MW3_SDK_SOURCE}/src" "${MW3_SDK_SOURCE}/tests" "${MW3_SDK_SOURCE}/tests/unit")
target_compile_definitions(thread-all-tests PRIVATE REX_TEST_REAL_MODULES)
target_link_libraries(thread-all-tests PRIVATE rex::sdk Catch2::Catch2WithMain)
rexglue_apply_target_settings(thread-all-tests)
rexglue_configure_target(thread-all-tests)
option(MW3_THREAD_SANITIZERS "Instrument test callbacks; SDK has its own receipt" OFF)
if(MW3_THREAD_SANITIZERS)
  foreach(target thread-platform-tests thread-kernel-tests thread-all-tests)
  if(WIN32)
    target_compile_options(${target} PRIVATE -fsanitize=undefined -fsanitize-trap=all -fno-sanitize=vptr)
    target_link_options(${target} PRIVATE -fsanitize=undefined -fsanitize-trap=all -fno-sanitize=vptr)
  else()
    target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-sanitize=vptr -fno-omit-frame-pointer)
    target_link_options(${target} PRIVATE -fsanitize=address,undefined -fno-sanitize=vptr)
  endif()
  endforeach()
endif()
