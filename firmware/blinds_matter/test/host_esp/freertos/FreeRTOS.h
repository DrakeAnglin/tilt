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
// A critical section: one task and no interrupts here, so it only checks that every enter has its exit (a second
// enter of the same lock, or an exit with no enter, is a fault).
typedef struct { int held; } portMUX_TYPE;
#define portMUX_INITIALIZER_UNLOCKED {0}
inline void portENTER_CRITICAL(portMUX_TYPE *m) { if (m->held++) host::fault("portENTER_CRITICAL on a lock already held"); }
inline void portEXIT_CRITICAL(portMUX_TYPE *m) { if (m->held-- <= 0) { m->held = 0; host::fault("portEXIT_CRITICAL with no enter"); } }
#define IRAM_ATTR
