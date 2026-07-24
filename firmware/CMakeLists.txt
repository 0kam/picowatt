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
    src/ina228.c
    src/ssd1306_ui.c
    src/proto.c
    src/ring.c
    src/sampler.c
    src/commands.c
    src/usb_descriptors.c
    lib/pico-ssd1306/ssd1306.c
)

target_include_directories(picowatt PRIVATE src lib/pico-ssd1306)

target_compile_options(picowatt PRIVATE -Wall -Wextra)

target_link_libraries(picowatt
    pico_stdlib
    pico_multicore
    pico_unique_id
    hardware_i2c
    tinyusb_device
    tinyusb_board
)

# Binary protocol uses TinyUSB CDC directly; no stdio over USB.
pico_enable_stdio_usb(picowatt 0)
pico_enable_stdio_uart(picowatt 0)

pico_add_extra_outputs(picowatt)
