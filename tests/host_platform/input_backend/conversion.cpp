// SPDX-License-Identifier: GPL-3.0-only
#include "input/backend/backend.hpp"
#include <iostream>
#include <stdexcept>
#include <string_view>

using namespace mw3::input;
namespace b = mw3::input::backend;
void check(bool value, const char* why) { if (!value) throw std::runtime_error(why); }
int main(int argc, char** argv) {
    if (argc != 2) { std::cerr << "ERROR: exactly one case required\n"; return 2; }
    const std::string_view name = argv[1];
    try {
        if (name == "axes") {
            const auto zero = b::convert(0, {});
            check(zero && zero->sticks == std::array<std::int16_t, 4>{}, "nonzero neutral");
            auto edge = b::convert(known_controls, {-32768, -32768, 32767, 32767, 0, 32767});
            check(edge && edge->buttons == known_controls && edge->sticks == std::array<std::int16_t, 4>{-32768, 32767, 32767, -32768}, "axis endpoints");
            auto middle = b::convert(0, {7, -1000, -9, 1000, 0, 0});
            check(middle && middle->sticks == std::array<std::int16_t, 4>{7, 999, -9, -1001}, "axis intermediates");
        } else if (name == "triggers") {
            for (int value = 0; value <= 32767; ++value) {
                auto sample = b::convert(0, {0, 0, 0, 0, static_cast<std::int16_t>(value), static_cast<std::int16_t>(32767 - value)});
                check(sample && sample->triggers[0] == value / 128 && sample->triggers[1] == (32767 - value) / 128, "trigger quantization");
            }
        } else if (name == "invalid") {
            check(!b::convert(known_controls + 1, {}), "unknown controls admitted");
            check(!b::convert(0, {0, 0, 0, 0, -1, 0}), "negative left trigger admitted");
            check(!b::convert(0, {0, 0, 0, 0, 0, -32768}), "negative right trigger admitted");
        } else if (name == "exhaustive") {
            int previous = 32768;
            for (int value = -32768; value <= 32767; ++value) {
                const int inverted = b::invert_y(static_cast<std::int16_t>(value));
                check(inverted <= previous && inverted >= -32768 && inverted <= 32767, "Y monotonicity/range");
                if (value == 0 || value == -1) check(inverted == 0, "Y neutral alias");
                else check(value + inverted == -1, "Y complement");
                previous = inverted;
            }
            check(b::invert_y(-32768) == 32767 && b::invert_y(32767) == -32768, "Y endpoint conversion");
        } else if (name == "negative-control") {
            check(b::convert(0, {})->sticks[1] == -1, "deliberate wrong-neutral rejected");
            throw std::runtime_error("wrong-neutral unexpectedly accepted");
        } else { std::cerr << "ERROR: unknown case\n"; return 2; }
        std::cout << "PASS: " << name << '\n'; return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
