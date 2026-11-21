// Bluetooth setup. A controller that has not been added to a home advertises over Bluetooth for 15 minutes after it
// starts (Matter does that). This adds one more service next to Matter's, for the blinds app:
//
//   service  B11D0001-7A3C-4F52-9E0D-6C2A91D4E5F0
//   RX       B11D0002-...   the app writes a request:  'H' hello | 'P' + pairing JSON | 'X' + sealed command
//   TX       B11D0003-...   the app then reads the answer:  status digit ('2' good, '4' refused) + answer
//
// Pairing and commands are exactly the ones in sec.h, so the Wi-Fi password travels sealed with the phone's key
// (/api/setwifi), never in the clear. A Bluetooth link by itself gives a stranger nothing once an owner exists.
#pragma once
#include <vector>
#include <host/ble_hs.h>
#include <host/ble_uuid.h>
#include <platform/internal/BLEManager.h>
#include "sec.h"

std::string helloJson();                         // web.h
static const ble_uuid128_t BLINDS_SVC = BLE_UUID128_INIT(0xF0, 0xE5, 0xD4, 0x91, 0x2A, 0x6C, 0x0D, 0x9E, 0x52, 0x4F, 0x3C, 0x7A, 0x01, 0x00, 0x1D, 0xB1);
static const ble_uuid128_t BLINDS_RX = BLE_UUID128_INIT(0xF0, 0xE5, 0xD4, 0x91, 0x2A, 0x6C, 0x0D, 0x9E, 0x52, 0x4F, 0x3C, 0x7A, 0x02, 0x00, 0x1D, 0xB1);
static const ble_uuid128_t BLINDS_TX = BLE_UUID128_INIT(0xF0, 0xE5, 0xD4, 0x91, 0x2A, 0x6C, 0x0D, 0x9E, 0x52, 0x4F, 0x3C, 0x7A, 0x03, 0x00, 0x1D, 0xB1);
static std::string bleAnswer = "2{}";
static uint16_t bleTxHandle = 0;

static int bleAccess(uint16_t, uint16_t, struct ble_gatt_access_ctxt *c, void *arg)
{
    if (c->op == BLE_GATT_ACCESS_OP_READ_CHR) return os_mbuf_append(c->om, bleAnswer.data(), bleAnswer.size()) == 0 ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
    if (c->op != BLE_GATT_ACCESS_OP_WRITE_CHR) return BLE_ATT_ERR_UNLIKELY;
    uint16_t n = OS_MBUF_PKTLEN(c->om), got = 0;
    if (n < 1 || n > 2300) return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    std::string in(n, 0), out;
    if (ble_hs_mbuf_to_flat(c->om, &in[0], n, &got) != 0) return BLE_ATT_ERR_UNLIKELY;
    const char *st = "400";
    if (in[0] == 'H') { out = helloJson(); st = "200"; }
    else if (in[0] == 'P') st = pairDo(in.substr(1), out);
    else if (in[0] == 'X') st = secDo(in.substr(1), out, nullptr);
    else out = "{\"err\":\"unknown request\"}";
    bleAnswer = std::string(1, st[0]) + out;
    return 0;
}
static const struct ble_gatt_chr_def bleChrs[] = {
    {.uuid = &BLINDS_RX.u, .access_cb = bleAccess, .arg = nullptr, .descriptors = nullptr, .flags = BLE_GATT_CHR_F_WRITE, .min_key_size = 0, .val_handle = nullptr, .cpfd = nullptr},
    {.uuid = &BLINDS_TX.u, .access_cb = bleAccess, .arg = nullptr, .descriptors = nullptr, .flags = BLE_GATT_CHR_F_READ, .min_key_size = 0, .val_handle = &bleTxHandle, .cpfd = nullptr},
    {}};
// Scan response: our service's UUID (so the app can scan for it) and a short name.
static const uint8_t bleScanRsp[] = {17, 0x07, 0xF0, 0xE5, 0xD4, 0x91, 0x2A, 0x6C, 0x0D, 0x9E, 0x52, 0x4F, 0x3C, 0x7A, 0x01, 0x00, 0x1D, 0xB1, 7, 0x09, 'B', 'l', 'i', 'n', 'd', 's'};

void bleSetupBegin()                             // before Matter starts
{
    std::vector<struct ble_gatt_svc_def> svcs;
    struct ble_gatt_svc_def s = {};
    s.type = BLE_GATT_SVC_TYPE_PRIMARY;
    s.uuid = &BLINDS_SVC.u;
    s.characteristics = bleChrs;
    svcs.push_back(s);
    auto &mgr = chip::DeviceLayer::Internal::BLEMgrImpl();
    mgr.ConfigureExtraServices(svcs, true);
    mgr.ConfigureScanResponseData(chip::ByteSpan(bleScanRsp, sizeof bleScanRsp));
}
