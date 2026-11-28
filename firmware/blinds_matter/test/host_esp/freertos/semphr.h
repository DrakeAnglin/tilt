// Stand-in for FreeRTOS's semphr.h on the host board (host_board.h): a mutex that knows if it is held (host::held).
// One task only: a second take (which would wait for ever) and a give with no take are faults. What another task did
// while this one waited for the lock (host::duringTake) runs inside the take, before the mutex is taken. Tests only.
#pragma once
#include "FreeRTOS.h"
typedef void *SemaphoreHandle_t;
inline SemaphoreHandle_t xSemaphoreCreateMutex() {
  host::board().mutexes.emplace_back();
  return &host::board().mutexes.back();
}
inline BaseType_t xSemaphoreTake(SemaphoreHandle_t m, TickType_t) {
  if (!m) { host::fault("xSemaphoreTake on no mutex"); return pdFALSE; }
  host::beforeTake(m);
  host::Mutex *x = (host::Mutex *)m;
  if (x->held) { host::fault("xSemaphoreTake on a mutex already held: the task would wait for ever"); return pdFALSE; }
  x->held = true;
  return pdTRUE;
}
inline BaseType_t xSemaphoreGive(SemaphoreHandle_t m) {
  if (!m) { host::fault("xSemaphoreGive on no mutex"); return pdFALSE; }
  host::Mutex *x = (host::Mutex *)m;
  if (!x->held) { host::fault("xSemaphoreGive on a mutex not taken"); return pdFALSE; }
  x->held = false;
  return pdTRUE;
}
