idf_component_register(SRC_DIRS "."
                       PRIV_INCLUDE_DIRS "." "${ESP_MATTER_PATH}/examples/common/utils")
target_compile_options(${COMPONENT_LIB} PRIVATE "-DCHIP_HAVE_CONFIG_H")
# A public release (tools/release_firmware.py) is built with no secrets at all: no Wi-Fi, no update password.
if(TILT_RELEASE)
  target_compile_definitions(${COMPONENT_LIB} PRIVATE TILT_RELEASE=1)
endif()
