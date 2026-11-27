// mbedtls settings for the hub test when tools/firmware_tests.sh builds ESP-IDF's copy of mbedtls: its own defaults,
// without the PSA layer (the checks use the plain ECDSA and SHA-256 calls, as the firmware does).
#undef MBEDTLS_PSA_CRYPTO_C
#undef MBEDTLS_PSA_CRYPTO_STORAGE_C
#undef MBEDTLS_PSA_ITS_FILE_C
#undef MBEDTLS_LMS_C
#undef MBEDTLS_SSL_TLS_C
#undef MBEDTLS_SSL_PROTO_TLS1_3
#undef MBEDTLS_SSL_CLI_C
#undef MBEDTLS_SSL_SRV_C
// The hub board test seals with AES-GCM (through the cipher layer): only AES is built, the other ciphers are left out.
#undef MBEDTLS_ARIA_C
#undef MBEDTLS_CAMELLIA_C
#undef MBEDTLS_DES_C
#undef MBEDTLS_CHACHA20_C
#undef MBEDTLS_CHACHAPOLY_C
#undef MBEDTLS_POLY1305_C
#undef MBEDTLS_CCM_C
#undef MBEDTLS_NIST_KW_C
#undef MBEDTLS_CMAC_C
