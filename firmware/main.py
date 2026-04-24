import machine
import binascii
import bluetooth
import time

# --- Configuration ---
adv_key_b64 = 'KKSh25lSRPxZbHRSOI2SP6j6qDPNW2koDvNTqg=='
sleep_ms = 5000  # 5 minutes
# ---------------------

def start_beacon():
    try:
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

        # Advertise
        ble.gap_advertise(100, adv_data=bytes(findmy_apple))
        
        # Broadcast duration
        time.sleep(3) 
        
        # --- HARD SAFETY SHUTDOWN ---
        ble.gap_advertise(None) # Stop advertising
        ble.active(False)       # Deactivate radio
        del ble                 # Remove object from memory
        
    except Exception as e:
        print(f"Error during broadcast: {e}")

# Execute broadcast
start_beacon()

print(f"Entering Deep Sleep for {sleep_ms}ms...")
time.sleep_ms(100) # Give Serial time to flush

# Final Deep Sleep Command
machine.deepsleep(sleep_ms)

# SAFETY FALLBACK: 
# If deepsleep fails to trigger (e.g. connected to certain chargers/USB),
# this loop prevents the CPU from running code and forces a reset.
while True:
    machine.reset()