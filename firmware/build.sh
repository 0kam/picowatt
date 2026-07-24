#!/bin/sh
# Build the picowatt firmware. Produces build/picowatt.uf2.
# Override PICO_SDK_PATH / PICO_TOOLCHAIN_PATH via env if yours live elsewhere.
set -e

: "${PICO_SDK_PATH:=$HOME/pico-sdk}"
: "${PICO_TOOLCHAIN_PATH:=$HOME/toolchains/arm-gnu-toolchain-15.2.rel1-darwin-arm64-arm-none-eabi}"
export PICO_SDK_PATH PICO_TOOLCHAIN_PATH

cd "$(dirname "$0")"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(sysctl -n hw.ncpu 2>/dev/null || echo 4)"
echo "OK: $(pwd)/build/picowatt.uf2"
