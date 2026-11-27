// Stand-in for FreeRTOS's FreeRTOS.h on the host board (host_board.h): the types and macros. Tests only.
// The tick is 1 ms, as in the controller's sdkconfig.defaults (CONFIG_FREERTOS_HZ=1000).
#pragma once
#include <cstdint>
#include "../host_board.h"
typedef uint32_t TickType_t;
typedef int BaseType_t;
typedef unsigned UBaseType_t;
#define pdTRUE 1
#define pdFALSE 0
#define pdPASS pdTRUE
#define configTICK_RATE_HZ 1000
#define portTICK_PERIOD_MS (1000 / configTICK_RATE_HZ)
#define portMAX_DELAY ((TickType_t)0xffffffffUL)
#define pdMS_TO_TICKS(ms) ((TickType_t)(((TickType_t)(ms) * (TickType_t)configTICK_RATE_HZ) / (TickType_t)1000U))
