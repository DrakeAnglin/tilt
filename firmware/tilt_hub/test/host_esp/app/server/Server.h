// Stand-in for the one Matter call hub_store.h makes (homeBeingAdded): whether a home app is adding the hub right now
// (the fail-safe is armed), as a test sets it on the board (hub_board.h). Not a stand-in for Matter: the rest of
// Matter goes behind the hub's own seam (#274), and this call with it. Tests only.
#pragma once
#include "../../hub_board.h"
namespace chip {
struct FailSafeContext {
  bool IsFailSafeArmed() const { return hubhost::hubBoard().failSafeArmed; }
};
class Server {
 public:
  static Server &GetInstance() { static Server s; return s; }
  FailSafeContext &GetFailSafeContext() { return failSafe; }
 private:
  FailSafeContext failSafe;
};
}  // namespace chip
