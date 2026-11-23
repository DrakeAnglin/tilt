idf_component_register(SRC_DIRS "."
                       PRIV_INCLUDE_DIRS "." "../../blinds_matter/main")
target_compile_options(${COMPONENT_LIB} PRIVATE "-DCHIP_HAVE_CONFIG_H")
