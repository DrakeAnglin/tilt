// Schedules (clock, sunrise, sunset) and gentle moves, run by the controller itself.
// Part of the web server (web.h includes it in place): uses its helpers and the blinds' shared state.
#pragma once

// ---- schedules (as in the Wi-Fi firmware's sleep.h, without the sleeping)
uint32_t lastSched = 0;
// Extra facts per schedule slot (kept beside the settings, so adding them did not disturb the saved marks):
//   kind 0 = at a clock time, 1 = at sunrise, 2 = at sunset (plus `off` minutes);  ramp = gentle: take this many minutes;
//   gid = the app's own number for a schedule, the same on every controller it covers.
struct SchedX { uint8_t kind, ramp; int16_t off; uint32_t gid; };
struct SchedExtra { uint32_t magic; SchedX x[SCHEDS]; float lat, lon; } sx;
const uint32_t SX_MAGIC = 0x53580001;
void sxSave() { nvs.putBytes("schx", &sx, sizeof sx); }
void sxLoad() {
  if (nvs.getBytes("schx", &sx, sizeof sx) != sizeof sx || sx.magic != SX_MAGIC) { memset(&sx, 0, sizeof sx); sx.magic = SX_MAGIC; sx.lat = sx.lon = NAN; }
}
// Sunrise or sunset (epoch seconds) on the day that holds `noon`, at the saved place (the math: logic.h).
uint32_t sunEvent(time_t noon, bool rise) { return sunEventAt(noon, sx.lat, sx.lon, rise); }
uint32_t schedTime(int i, time_t now, int dayOff) {      // when slot i fires on (today + dayOff); 0 = not that day
  const Sched &s = cfg.sched[i];
  struct tm tm, chk;
  localtime_r(&now, &tm);
  tm.tm_mday += dayOff;
  tm.tm_hour = sx.x[i].kind ? 12 : 0; tm.tm_min = sx.x[i].kind ? 0 : s.minute; tm.tm_sec = 0; tm.tm_isdst = -1;
  time_t t = mktime(&tm);
  localtime_r(&t, &chk);
  if (!((s.days >> chk.tm_wday) & 1)) return 0;
  if (!sx.x[i].kind) return (uint32_t)t;
  uint32_t e = sunEvent(t, sx.x[i].kind == 1);
  return e ? e + sx.x[i].off * 60 : 0;
}
// Gentle moves: a blind that is being taken to a tilt slowly, a little every 20 seconds.
struct Ramp { bool on; float from, to; uint32_t t0, durMs, last; } ramp[PORTS];
void rampCancel() { for (auto &r : ramp) r.on = false; }
bool rampAny() { for (auto &r : ramp) if (r.on) return true; return false; }
void rampTick() {
  uint32_t now = millis();
  for (int p = 0; p < PORTS; p++) {
    Ramp &r = ramp[p];
    if (!r.on || now - r.last < 20000 || moving()) continue;
    r.last = now;
    float f = min(1.0f, (float)(now - r.t0) / r.durMs);
    startTilt(p, r.from + (r.to - r.from) * f);
    if (f >= 1.0f) r.on = false;
  }
}
void schedRun() {
  if (!timeValid()) return;
  uint32_t now = time(nullptr);
  if (lastSched > now || now - lastSched > 1800) lastSched = now - 90;
  for (int i = 0; i < SCHEDS; i++) {
    Sched &s = cfg.sched[i];
    if (!s.on) continue;
    for (int d = -1; d <= 0; d++) {
      uint32_t t = schedTime(i, now, d);
      if (t && t > lastSched && t <= now) {
        event("schedule %d: tilt %d", i + 1, s.tilt);
        for (int p = 0; p < PORTS; p++) {
          if (!((s.mask >> p) & 1) || !movable(p)) continue;
          if (sx.x[i].ramp && !isnan(bs[p].tilt)) ramp[p] = {true, bs[p].tilt, (float)s.tilt, millis(), (uint32_t)sx.x[i].ramp * 60000u, 0};
          else startTilt(p, s.tilt);
        }
      }
    }
  }
  lastSched = now;
}
uint32_t schedNext() {
  if (!timeValid()) return 0;
  uint32_t now = time(nullptr), best = 0;
  for (int i = 0; i < SCHEDS; i++) {
    if (!cfg.sched[i].on) continue;
    for (int d = 0; d <= 7; d++) {
      uint32_t t = schedTime(i, now, d);
      if (t > now) { if (!best || t < best) best = t; break; }
    }
  }
  return best;
}
