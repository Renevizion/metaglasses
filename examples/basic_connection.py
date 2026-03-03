"""
Example: Basic connection to Ray-Ban Meta Smart Glasses.

Run with:
    python examples/basic_connection.py
"""

from metaglasses import Glasses, GlassesConnectionError


def main():
    glasses = Glasses(device_name="Ray-Ban Meta", timeout=10.0)

    print("Connecting to glasses…")
    try:
        glasses.connect()
    except GlassesConnectionError as exc:
        print(f"[ERROR] {exc}")
        return

    print("Connected!")
    status = glasses.status()
    print(f"  Firmware  : {status['firmware']}")
    print(f"  Battery   : {status['battery_pct']}%")
    print(f"  Storage   : {status['storage_used_mb']:.1f} / {status['storage_total_mb']:.1f} MB")
    print(f"  Mode      : {status['capture_mode']}")
    print(f"  Charging  : {status['is_charging']}")

    glasses.disconnect()
    print("Disconnected.")


if __name__ == "__main__":
    main()
