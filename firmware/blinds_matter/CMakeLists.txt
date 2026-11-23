# Blinds controller with Matter over Thread (Apple Home, Alexa). ESP-IDF v5.5.5 + esp-matter release/v1.5.
#   . ~/esp/esp-idf/export.sh && . ~/esp/esp-matter/export.sh && idf.py set-target esp32c6 && idf.py build
cmake_minimum_required(VERSION 3.5)
if(NOT DEFINED ENV{ESP_MATTER_PATH})
    message(FATAL_ERROR "Please set ESP_MATTER_PATH to the path of esp-matter repo")
endif()
# The version inside the image (what an update is checked against) is FW_VERSION from main/web.h: one place only.
file(STRINGS "${CMAKE_CURRENT_LIST_DIR}/main/web.h" FW_VERSION_LINE REGEX "^#define FW_VERSION ")
string(REGEX REPLACE ".*\"([^\"]+)\".*" "\\1" PROJECT_VER "${FW_VERSION_LINE}")
set(PROJECT_VER_NUMBER 4)
# A dev build ("-devN") also keeps the hourly power log (main/store.h, /api/powerlog).
if(PROJECT_VER MATCHES "-dev")
  add_compile_definitions(TILT_DEVLOG=1)
endif()
set(ESP_MATTER_PATH $ENV{ESP_MATTER_PATH})
set(MATTER_SDK_PATH ${ESP_MATTER_PATH}/connectedhomeip/connectedhomeip)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
set(EXTRA_COMPONENT_DIRS
    "${ESP_MATTER_PATH}/examples/common"
    "${MATTER_SDK_PATH}/config/esp32/components"
    "${ESP_MATTER_PATH}/components")
project(blinds_matter)
idf_build_set_property(CXX_COMPILE_OPTIONS "-std=gnu++17;-Os;-DCHIP_HAVE_CONFIG_H;-DCONFIG_OPENTHREAD_CONFIG_SRP_CLIENT_BUFFERS_MAX_SERVICES=5;-Wno-overloaded-virtual" APPEND)
idf_build_set_property(C_COMPILE_OPTIONS "-Os;-DCONFIG_OPENTHREAD_CONFIG_SRP_CLIENT_BUFFERS_MAX_SERVICES=5" APPEND)
idf_build_set_property(COMPILE_OPTIONS "-Wno-format-nonliteral;-Wno-format-security" APPEND)
