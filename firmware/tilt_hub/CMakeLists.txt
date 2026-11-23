# Tilt Hub: an ESP32-C6 on a USB wall plug. Apple Home sees the blinds through it (Matter over Wi-Fi), and the
# controllers talk to it over its own Thread network, so they can sleep. ESP-IDF v5.5.5 + esp-matter release/v1.5.
#   ./build.sh            ./build.sh -p /dev/cu.usbmodemXXXX flash monitor
cmake_minimum_required(VERSION 3.5)
if(NOT DEFINED ENV{ESP_MATTER_PATH})
    message(FATAL_ERROR "Please set ESP_MATTER_PATH to the path of esp-matter repo")
endif()
set(PROJECT_VER "0.2.2")                         # the hub's version: raise it for every hub update
set(PROJECT_VER_NUMBER 1)
set(ESP_MATTER_PATH $ENV{ESP_MATTER_PATH})
set(MATTER_SDK_PATH ${ESP_MATTER_PATH}/connectedhomeip/connectedhomeip)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
set(EXTRA_COMPONENT_DIRS
    "${ESP_MATTER_PATH}/examples/common"
    "${MATTER_SDK_PATH}/config/esp32/components"
    "${ESP_MATTER_PATH}/components")
project(tilt_hub)
idf_build_set_property(CXX_COMPILE_OPTIONS "-std=gnu++17;-Os;-DCHIP_HAVE_CONFIG_H;-Wno-overloaded-virtual" APPEND)
idf_build_set_property(C_COMPILE_OPTIONS "-Os" APPEND)
idf_build_set_property(COMPILE_OPTIONS "-Wno-format-nonliteral;-Wno-format-security" APPEND)
