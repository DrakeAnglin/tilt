// This controller's own Apple Home (Matter) setup code. Made at random on the first start and kept in flash, so it
// never changes: a controller already in a home keeps working, and the code the owner saw stays good. Without this,
// every controller would answer to the public SDK test code (20202021).
#pragma once
#include <string>
#include <esp_random.h>
#include <bootloader_random.h>
#include <esp_matter_providers.h>
#include <platform/CommissionableDataProvider.h>
#include <crypto/CHIPCryptoPAL.h>
#include <setup_payload/SetupPayload.h>
#include <setup_payload/ManualSetupPayloadGenerator.h>
#include <setup_payload/QRCodeSetupPayloadGenerator.h>
#include "logic.h"                               // HomeCode, homeCodeKeep
#include "store.h"                               // nvs, event

static_assert(sizeof(HomeCode::verifier) == chip::Crypto::kSpake2p_VerifierSerialized_Length, "verifier size");
HomeCode homeCode;

// What Matter asks for when a home adds this controller. The code itself cannot be changed from outside.
struct HomeCodeProvider : chip::DeviceLayer::CommissionableDataProvider {
  CHIP_ERROR GetSetupDiscriminator(uint16_t &d) override { d = homeCode.disc; return CHIP_NO_ERROR; }
  CHIP_ERROR SetSetupDiscriminator(uint16_t) override { return CHIP_ERROR_NOT_IMPLEMENTED; }
  CHIP_ERROR GetSpake2pIterationCount(uint32_t &n) override { n = homeCode.iter; return CHIP_NO_ERROR; }
  CHIP_ERROR GetSpake2pSalt(chip::MutableByteSpan &b) override { return chip::CopySpanToMutableSpan(chip::ByteSpan(homeCode.salt), b); }
  CHIP_ERROR GetSpake2pVerifier(chip::MutableByteSpan &b, size_t &n) override {
    n = sizeof homeCode.verifier;
    return chip::CopySpanToMutableSpan(chip::ByteSpan(homeCode.verifier), b);
  }
  CHIP_ERROR GetSetupPasscode(uint32_t &p) override { p = homeCode.pin; return CHIP_NO_ERROR; }
  CHIP_ERROR SetSetupPasscode(uint32_t) override { return CHIP_ERROR_NOT_IMPLEMENTED; }
};
HomeCodeProvider homeCodeProvider;

// Before Bluetooth and Matter start (the random source is only good while the radio is off).
void homeCodeBegin() {
  if (!homeCodeKeep(homeCode, nvs.getBytes("homecode", &homeCode, sizeof homeCode))) {
    HomeCode c = {HOME_CODE_MAGIC, 0, 1000, 0, {}, {}};
    bootloader_random_enable();
    do esp_fill_random(&c.pin, sizeof c.pin); while (!setupPinValid(c.pin %= 100000000));
    esp_fill_random(&c.disc, sizeof c.disc);
    c.disc &= 0xFFF;
    esp_fill_random(c.salt, sizeof c.salt);
    bootloader_random_disable();
    chip::Crypto::Spake2pVerifier v;
    chip::MutableByteSpan out(c.verifier);
    if (v.Generate(c.iter, chip::ByteSpan(c.salt), c.pin) == CHIP_NO_ERROR && v.Serialize(out) == CHIP_NO_ERROR) {
      homeCode = c;
      nvs.putBytes("homecode", &homeCode, sizeof homeCode);
      event("new Apple Home setup code made");
    } else {
      event("could not make an Apple Home setup code");
    }
  }
  esp_matter::set_custom_commissionable_data_provider(&homeCodeProvider);
}

// {"ok":1,"code":"xxxx-xxx-xxxx","qr":"MT:..."}: the code to type and the QR text, for Bluetooth setup.
std::string homeCodeJson() {
  chip::PayloadContents p;
  p.vendorID = CONFIG_DEVICE_VENDOR_ID;
  p.productID = CONFIG_DEVICE_PRODUCT_ID;
  p.rendezvousInformation.Emplace(chip::RendezvousInformationFlag::kBLE);
  p.discriminator.SetLongValue(homeCode.disc);
  p.setUpPINCode = homeCode.pin;
  char manual[chip::kManualSetupLongCodeCharLength + 1], qr[chip::QRCodeBasicSetupPayloadGenerator::kMaxQRCodeBase38RepresentationLength + 1];
  chip::MutableCharSpan m(manual), q(qr);
  if (chip::ManualSetupPayloadGenerator(p).payloadDecimalStringRepresentation(m) != CHIP_NO_ERROR ||
      chip::QRCodeBasicSetupPayloadGenerator(p).payloadBase38Representation(q) != CHIP_NO_ERROR)
    return "{\"err\":\"no setup code\"}";
  return "{\"ok\":1,\"code\":\"" + manualCodeDashed(std::string(m.data(), m.size())) + "\",\"qr\":\"" + std::string(q.data(), q.size()) + "\"}";
}
