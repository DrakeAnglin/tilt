// Made from firmware/blinds-settings-backup.json: the marks and names that were on the board before the USB flash.
// Used once, when the board starts with empty storage.
#pragma once
inline void restoreBackup() {
  strlcpy(cfg.name, "Blinds", sizeof cfg.name);
  cfg.closeUp = 1; cfg.battMode = 0; cfg.checkinMin = 15;
  strlcpy(cfg.tz, "CST6CDT,M3.2.0,M11.1.0", sizeof cfg.tz); strlcpy(cfg.tzName, "America/Chicago", sizeof cfg.tzName);
  strlcpy(cfg.b[0].name, "Blind 1", sizeof cfg.b[0].name);
  cfg.b[0].up = 204.0f; cfg.b[0].open = 288.7f; cfg.b[0].down = 42.3f; cfg.b[0].motSign = 2; cfg.b[0].speed = 100; cfg.b[0].fav = 0; cfg.b[0].hidden = 0;
  strlcpy(cfg.b[1].name, "Blind 2", sizeof cfg.b[1].name);
  cfg.b[1].up = NAN; cfg.b[1].open = NAN; cfg.b[1].down = NAN; cfg.b[1].motSign = 1; cfg.b[1].speed = 100; cfg.b[1].fav = 50; cfg.b[1].hidden = 0;
  strlcpy(cfg.b[2].name, "Blind 3", sizeof cfg.b[2].name);
  cfg.b[2].up = NAN; cfg.b[2].open = NAN; cfg.b[2].down = NAN; cfg.b[2].motSign = 1; cfg.b[2].speed = 100; cfg.b[2].fav = 50; cfg.b[2].hidden = 0;
}
