cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD pico2 CACHE STRING "Board type")

# Pull in pico-sdk (must be before project())
include(pico_sdk_import.cmake)

project(picowatt C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(picowatt
    src/main.c
)

target_include_directories(picowatt PRIVATE src)

target_compile_options(picowatt PRIVATE -Wall -Wextra)

target_link_libraries(picowatt
    pico_stdlib
    hardware_i2c
)

# M1: USB CDC via stdio for text output / echo.
# Replaced by a custom TinyUSB CDC device in M4 (binary protocol).
pico_enable_stdio_usb(picowatt 1)
pico_enable_stdio_uart(picowatt 0)

pico_add_extra_outputs(picowatt)
