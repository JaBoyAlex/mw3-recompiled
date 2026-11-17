# The pinned XenonRecomp root selects C++17 but includes C++20 library facilities.
# CMAKE_PROJECT_INCLUDE applies after project() without editing the research checkout.
# This override is for the host analysis/code-generation tools, not translated game code.
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
