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
