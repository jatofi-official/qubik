import base64
import json
import requests
import struct
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import argparse

# PARSER
parser = argparse.ArgumentParser(add_help=True, description="Script used for getting and decrypting macless-haystack output for a single tag. Outputs data in json format.")

parser.add_argument("hashed_key", help="Public tag key for getting data.")
parser.add_argument("private_key", help="Private tag key for decrypting.")
parser.add_argument("--verbose", "-v", action ="store_true", help="Prints more information, does not print json. Used for manual testing.")
parser.add_argument('-time', '-t', help='How many days to get results from. Default is 7', default=7, type=int)
args = parser.parse_args()

# CONFIGURATION
PRIV_KEY_B64 = args.private_key
ADV_KEY_HASHED = args.hashed_key
ENDPOINT = "http://localhost:6176/"

# This code is rewriten from dart. I have used AI to help me, since I don't understand the complicated math going on.
# This is the original code: https://github.com/dchristl/macless-haystack/blob/0bda271b8bd0cc37194dfba1845cd48954cba4cc/macless_haystack/lib/findMy/decrypt_reports.dart#L4
def decrypt_report(payload_b64, priv_key_b64):
    priv_bytes = base64.b64decode(priv_key_b64)
    payload = base64.b64decode(payload_b64)

    # 1. Handle Macless-specific data modification (from the Dart code)
    if len(payload) > 88:
        # It removes one byte at index 4 if length > 88
        payload = payload[0:4] + payload[5:]

    # 2. Slice data exactly like Dart
    # Index 4 is the confidence byte in the modified payload
    confidence = payload[4]
    ephemeral_key_bytes = payload[5:62]
    enc_data = payload[62:72]  # 10 bytes (lat+lon+acc+status)
    tag = payload[72:]        # The rest is the GCM tag

    # 3. Setup Private Key
    priv_val = int.from_bytes(priv_bytes, 'big')
    priv_key = ec.derive_private_key(priv_val, ec.SECP224R1())

    # 4. Load Ephemeral Public Key
    ephemeral_pub_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP224R1(), ephemeral_key_bytes)

    # 5. ECDH Shared Secret
    shared_secret = priv_key.exchange(ec.ECDH(), ephemeral_pub_key)

    # 6. Custom ANSI X9.63 KDF (Match Dart's _kdf)
    sha256 = hashes.Hash(hashes.SHA256())
    sha256.update(shared_secret)
    sha256.update(struct.pack('>I', 1)) 
    sha256.update(ephemeral_key_bytes)
    derived_key = sha256.finalize()

    aes_key = derived_key[:16]
    iv = derived_key[16:32]

    # 7. AES-GCM Decrypt
    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv, tag))
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(enc_data) + decryptor.finalize()

    # 8. Decode Location and Status
    lat_raw = struct.unpack('>I', decrypted[0:4])[0]
    lon_raw = struct.unpack('>I', decrypted[4:8])[0]
    accuracy = decrypted[8]
    status = decrypted[9]

    # --- Battery decoding ---
    # Shift right 6 bits to get the top 2 bits (0-3)
    battery_code = status >> 6
    battery_levels = {0: "Full/OK", 1: "Medium", 2: "Low", 3: "Critical Low"}
    battery = battery_levels.get(battery_code, "Unknown")

    # Handle signedness for Lat/Lon
    lat = (lat_raw if lat_raw < 0x80000000 else lat_raw - 0x100000000) / 10000000.0
    lon = (lon_raw if lon_raw < 0x80000000 else lon_raw - 0x100000000) / 10000000.0

    # 9. Decode Time (Apple Epoch is 2001)
    seen_time_raw = struct.unpack('>i', payload[0:4])[0]
    timestamp = datetime(2001, 1, 1) + timedelta(seconds=seen_time_raw)

    return lat, lon, timestamp, accuracy, battery, confidence

# EXECUTION
DAYS_BACK = args.time
verbose = args.verbose 

if verbose:
    print("Verbose mode is on")
    print(f"Connecting to {ENDPOINT}...")

try:
    # requesting data
    request_data = {
        'ids': [ADV_KEY_HASHED],
        'days': DAYS_BACK
    }
    
    r = requests.post(ENDPOINT, json=request_data)
    results = r.json().get('results', [])
    
    if verbose:
        print(f"Found {len(results)} reports from the last {DAYS_BACK} days. Decrypting...\n")
    
    for res in results:
        try:
            lat, lon, time, acc, battery, confidence = decrypt_report(res['payload'], PRIV_KEY_B64)

            # Filter out noise if any
            if lat == 0 and lon == 0:
                continue
            
            if verbose:
                print(f"Time: {time} (UTC) | Acc: {acc}m")
                print(f"Pos:  {lat}, {lon}")
                print(f"Battery:  {battery}")
                print(f"Confidence:  {confidence}")
                print(f"Map:  https://www.google.com/maps/search/?api=1&query={lat},{lon}")
                print("-" * 40)
            else:
                output_data = {
                    "time" : time.isoformat(),
                    "latitude" : lat,
                    "longitude" : lon,
                    "accuracy" : acc,
                    "battery" : battery,
                    "confidence" : confidence
                }
                print(json.dumps(output_data))

        except Exception as e:
            print(f"Exception: {e}")

except Exception as e:
    print(f"Network error: {e}")
