// Stand-in for FreeRTOS's task.h on the host board (host_board.h): a delay moves the board's clock. What another task
// does meanwhile (host::duringDelay) runs inside it, before the clock moves. Tests only.
#pragma once
#include "FreeRTOS.h"
inline void vTaskDelay(TickType_t ticks) {
  if (host::board().delayHook) {
    std::function<void()> fn = host::board().delayHook;
    host::board().delayHook = nullptr;                 // once: fn may set the next one
    fn();
  }
  host::advanceMs((int64_t)ticks * portTICK_PERIOD_MS);
}
