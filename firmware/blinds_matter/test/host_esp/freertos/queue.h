// Stand-in for FreeRTOS's queue.h on the host board (host_board.h): a queue of fixed-size items, one task only. A send
// to a full queue and a receive from an empty one return at once (nothing else could fill or empty it), whatever the
// wait. A test fills it and reads it with the same calls the firmware uses. Tests only.
#pragma once
#include <deque>
#include <vector>
#include "FreeRTOS.h"
struct HostQueue { size_t len, size; std::deque<std::vector<uint8_t>> items; };
typedef HostQueue *QueueHandle_t;
inline QueueHandle_t xQueueCreate(UBaseType_t len, UBaseType_t size) { return new HostQueue{len, size, {}}; }
inline BaseType_t xQueueSend(QueueHandle_t q, const void *item, TickType_t) {
  if (!q) { host::fault("xQueueSend on no queue"); return pdFALSE; }
  if (q->items.size() >= q->len) return pdFALSE;
  q->items.emplace_back((const uint8_t *)item, (const uint8_t *)item + q->size);
  return pdTRUE;
}
inline BaseType_t xQueueReceive(QueueHandle_t q, void *item, TickType_t) {
  if (!q) { host::fault("xQueueReceive on no queue"); return pdFALSE; }
  if (q->items.empty()) return pdFALSE;
  memcpy(item, q->items.front().data(), q->size);
  q->items.pop_front();
  return pdTRUE;
}
inline BaseType_t xQueueReset(QueueHandle_t q) { if (q) q->items.clear(); return pdPASS; }
inline UBaseType_t uxQueueMessagesWaiting(QueueHandle_t q) { return q ? (UBaseType_t)q->items.size() : 0; }
