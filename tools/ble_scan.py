#!/usr/bin/env python3
"""Find blinds controllers that are waiting for Bluetooth setup, and say hello to the first one. Needs 'bleak'."""
import asyncio, sys
from bleak import BleakScanner, BleakClient
SVC = 'b11d0001-7a3c-4f52-9e0d-6c2a91d4e5f0'; RX = 'b11d0002-7a3c-4f52-9e0d-6c2a91d4e5f0'; TX = 'b11d0003-7a3c-4f52-9e0d-6c2a91d4e5f0'
async def main():
    found = await BleakScanner.discover(timeout=8.0, return_adv=True)
    mine = [(d, a) for d, a in found.values() if SVC in [u.lower() for u in a.service_uuids] or (a.local_name or '').startswith('Blinds')]
    print('devices seen: %d, blinds controllers: %d' % (len(found), len(mine)))
    for d, a in mine: print('  ', a.local_name, a.rssi, 'dBm', a.service_uuids)
    if not mine: return
    async with BleakClient(mine[0][0]) as c:
        await c.write_gatt_char(RX, b'H', response=True)
        print('hello:', (await c.read_gatt_char(TX)).decode())
asyncio.run(main())
