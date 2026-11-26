# Security hardening for later

The firmware already protects the network side: every phone command is sealed with that phone's own key, messages
between the Tilt Hub and a controller carry a proof made from the hub's key, firmware must be signed and not older
than what runs, and the hub's first owner needs the setup code on its label. What is left is **someone holding a
device with a USB cable**: today they can read everything stored on it.

Do these before selling devices or giving them away. Each one is hard or impossible to undo on a chip (eFuses), so
try them on a spare board first.

## 1. Flash encryption (controller and hub)

What it fixes: the flash holds every phone key, the hub's keys on the controllers, the Thread network key, Matter's
fabric keys and the Apple Home setup code. Without encryption, `esptool read_flash` copies them all.

- `CONFIG_SECURE_FLASH_ENC_ENABLED=y`, in **Release** mode for devices that leave the bench (Development mode can be
  turned off again, Release cannot).
- Mark the hub's `fwstage` partition `encrypted` in `partitions.csv`.
- After this, updates over USB need the encrypted flow; updates through the hub keep working.

## 2. NVS encryption

What it fixes: NVS (the keys, settings and Thread dataset) is not covered by flash encryption by itself.

- `CONFIG_NVS_ENCRYPTION=y`, with the keys in the `nvs_keys` partition (the controller already has one; add one to
  the hub's partition table), or the HMAC-based scheme (`CONFIG_NVS_SEC_KEY_PROTECT_USING_HMAC`) so no key partition
  is needed.

## 3. Secure boot v2

What it fixes: with physical access someone can flash their own firmware over USB, which would then be trusted by the
app and the hub. Secure boot only runs firmware signed with our key.

- `CONFIG_SECURE_BOOT=y` (v2, ECDSA P-256). Use a separate secure-boot key from the release signing key in
  `~/.tilt/`.
- With it, turn on anti-rollback (`CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK`) and raise `secure_version` with each release
  that fixes a security bug. (The app-level check in `logic.h fwIsOlder` already refuses older firmware through the
  hub; this makes it hold against USB too.)

## 4. Turn off USB JTAG and the ROM download mode

- Burn `DIS_USB_JTAG` (and `DIS_PAD_JTAG`) once boards are past the bench.
- `CONFIG_SECURE_UART_ROM_DL_MODE=y` (Secure Download Mode): flashing over USB still works, reading flash does not.

## 5. Matter device attestation

The builds use Espressif's test attestation (`CONFIG_EXAMPLE_DAC_PROVIDER=y`, vendor 0xFFF1, product 0x8000). That is
why Apple Home says "Uncertified Accessory". A product needs its own vendor id, a real DAC/PAI from a Matter PKI
provider, and Matter certification.

## 6. Logs and secrets on the bench

- The hub's USB log prints the Thread dataset and the Apple Home setup code (`hub.cpp` threadBegin, `hub_matter.h`
  homeCodeBegin). Remove those lines, or show them only in a debug build.
- `main/secrets.h` (Wi-Fi, bench only) and `main/setup_pin.h` (the hub's setup code) stay out of Git. Each hub
  needs its own setup code: run a clean build per hub (delete `setup_pin.h`) and print the label from it.

## 7. Network key changes

A phone that was an owner once could have read the hub's Thread network key. Removing it from the hub does not
change that key. Later: a "new network key" button on the hub page that rolls the Thread dataset and hands the new
one to each controller.

## Smaller items left from the 2026-11 review

- A user (not an owner) can read a controller's backup, which includes the home's latitude and longitude. Users are
  trusted; strip the location if that changes.
