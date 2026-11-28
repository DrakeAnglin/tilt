// A simulated tilter rod, for the tests: the rod, the gear play between it and the motor, the motor's speed, hard
// stops, and which way the motor turns it. One model of the rod for both test programs: logic_test.cpp's SimTilter
// (behind the Tilter seam) and test/host_esp/host_tilter.h (behind the host board's pins). Tests only.
#pragma once
#include <algorithm>
#include <cmath>

struct Rod {
  float rod = 290, gear = 290;  // the rod's true angle; where the motor side of the gear play is
  float play = 5;               // gear play, degrees of rod turn
  float degPerS = 2.5f;         // at full duty
  int phys = 1;                 // +1: motor "forward" makes the angle rise
  float lo = -1e9f, hi = 1e9f;  // hard stops (unwrapped degrees)
  float rodMin = 1e9f, rodMax = -1e9f;   // how far the rod went, either way
  // The motor turns dir (-1 / 0 / +1) at duty percent for dtMs: the motor side moves, and takes the rod along once
  // the gear play is taken up; the rod stops at its hard stops.
  void turn(int dir, int duty, float dtMs) {
    gear += phys * dir * degPerS * duty / 100.0f * dtMs / 1000.0f;
    if (gear > rod + play / 2) rod = gear - play / 2;
    if (gear < rod - play / 2) rod = gear + play / 2;
    if (rod > hi) rod = hi;
    if (rod < lo) rod = lo;
    gear = std::min(std::max(gear, rod - play / 2), rod + play / 2);
    rodMin = std::min(rodMin, rod); rodMax = std::max(rodMax, rod);
  }
  float wrapped() const { return fmodf(fmodf(rod, 360.0f) + 360.0f, 360.0f); }   // the angle the sensor sees, 0..360
};
