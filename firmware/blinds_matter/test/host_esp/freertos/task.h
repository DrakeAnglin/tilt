// Stand-in for FreeRTOS's task.h on the host board (host_board.h): a delay moves the board's clock. Tests only.
#pragma once
#include "FreeRTOS.h"
inline void vTaskDelay(TickType_t ticks) { host::advanceMs((int64_t)ticks * portTICK_PERIOD_MS); }
