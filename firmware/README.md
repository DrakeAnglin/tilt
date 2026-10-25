# Firmware

ESP32-S3, Arduino-ESP32 core 3.x (PlatformIO). Not started. See [architecture](../docs/architecture.md#firmware-overview-details-later-in-firmware).

Planned modules: `motor` (PWM + PCNT encoder + motion profile + stall detection), `calibration`, `storage` (NVS),
`matter_bridge` (MatterWindowCovering endpoints), `web` (HTTP/WebSocket API + hosted setup app), `ota`, `button_led`.

First milestone: spin one N20 to an encoder target with soft start/stop at 20 kHz PWM and stop on stall.
