idf_component_register(SRC_DIRS "."
                       PRIV_INCLUDE_DIRS "." "../../blinds_matter/main")
target_compile_options(${COMPONENT_LIB} PRIVATE "-DCHIP_HAVE_CONFIG_H")
# The hub's own log keeps its info lines; the rest of the firmware is built with warnings and errors only (#108).
target_compile_definitions(${COMPONENT_LIB} PRIVATE LOG_LOCAL_LEVEL=ESP_LOG_INFO)
# A public release (tools/release_firmware.py --hub) has no setup code in it: each hub keeps its own in flash.
if(TILT_RELEASE)
  target_compile_definitions(${COMPONENT_LIB} PRIVATE TILT_RELEASE=1)
endif()
