// The controller lock, mx: one FreeRTOS mutex for the blinds' shared state.
//
//   What it protects: the settings and counters (cfg, stats, tune, sx, battHist, the follow modes), every blind's
//   state and Move (bs[], mvs[], ramp[], the watch and hand-turn state, the move trace), the phones (keys[],
//   lastCtr[]) and the recovery attempt (recover).
//   Who holds it: the blinds task for each pass of its loop (so webTick, schedRun, rampTick and recoverTick run under
//   it), every web handler through Lock (api.h), and pairing and secured commands through KeysLock (sec.h).
//   The mark's steady reading (motion.h setMark) lets the lock go for each of its 50 ms waits (Unlocked, below).
//   Not under it: the event log (its own lock, store.h) and Matter's pend[] (one word per covering, app_main.cpp).
//
// Lock order: secMx (sec.h), then mx, then the event log's lock. Nothing that holds mx may take secMx.
#pragma once
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

SemaphoreHandle_t mx = nullptr;
void lockBegin() { mx = xSemaphoreCreateMutex(); }

// Gives mx back for the rest of the scope and takes it again when the scope ends. Only for one who holds mx; shared
// state read before it may have changed after it.
struct Unlocked {
  Unlocked() { xSemaphoreGive(mx); }
  ~Unlocked() { xSemaphoreTake(mx, portMAX_DELAY); }
};
