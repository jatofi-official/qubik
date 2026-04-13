import machine
import binascii
import bluetooth
import time

# --- Configuration ---
adv_key_b64 = '/hryBI34cKFFb5f+Ay2G4I2M++yW6DyWRTbaww=='
sleep_ms = 300000  # 5 minutes (300,000 ms)
# ---------------------

public_key = list(binascii.a2b_base64(adv_key_b64))

# Prepare the payload
findmy_apple = [
    0x1e, 0xff, 0x4c, 0x00, 0x12, 0x19, 0x00,
] + public_key[-22:] + [0x00, 0x00]

ble_mac = [public_key[0] | 0xc0] + public_key[1:6]
findmy_apple[29] = public_key[0] >> 6

# Set MAC address
machine.base_mac_addr(bytearray(ble_mac[:-1] + [ble_mac[-1] - 2]))

# Start BLE
ble = bluetooth.BLE()
ble.active(True)

# Advertise for a brief moment (usually 1-2 seconds to ensure it's picked up)
# Then immediately go to sleep
ble.gap_advertise(100, adv_data=bytes(findmy_apple))
time.sleep(2) # Give the radio a moment to actually broadcast
ble.active(False)

print(f"Going to sleep for {sleep_ms}ms...")
machine.deepsleep(sleep_ms)
