"""Inject (or clear) anomalies for the sensor simulator.

CLI usage:
    python anomaly_injector.py compressor-01 vibration
    python anomaly_injector.py compressor-01 vibration --intensity 5.0
    python anomaly_injector.py --clear
"""

import argparse
import json
import os
import time


ANOMALY_FILE = "/tmp/anomaly_target.json"


def inject_anomaly(machine_id: str, sensor_type: str, intensity: float = 3.0):
    """Write an anomaly target file so the sensor producer picks it up."""
    payload = {
        "machine_id": machine_id,
        "sensor_type": sensor_type,
        "start_time": time.time(),
        "intensity": intensity,
    }
    with open(ANOMALY_FILE, "w") as f:
        json.dump(payload, f)
    print(f"Anomaly injected: {machine_id} / {sensor_type} "
          f"(intensity={intensity}). Ramps up over ~60 s.")


def clear_anomaly():
    """Remove the anomaly target file to return to normal readings."""
    if os.path.exists(ANOMALY_FILE):
        os.remove(ANOMALY_FILE)
        print("Anomaly cleared. Readings will return to normal.")
    else:
        print("No active anomaly to clear.")


def main():
    parser = argparse.ArgumentParser(description="Inject or clear sensor anomalies.")
    parser.add_argument("machine_id", nargs="?", help="Target machine ID (e.g. compressor-01)")
    parser.add_argument("sensor_type", nargs="?", help="Target sensor type (e.g. vibration)")
    parser.add_argument("--intensity", type=float, default=3.0,
                        help="Anomaly intensity multiplier (default: 3.0)")
    parser.add_argument("--clear", action="store_true", help="Clear any active anomaly")

    args = parser.parse_args()

    if args.clear:
        clear_anomaly()
    elif args.machine_id and args.sensor_type:
        inject_anomaly(args.machine_id, args.sensor_type, args.intensity)
    else:
        parser.error("Provide machine_id and sensor_type, or use --clear.")


if __name__ == "__main__":
    main()
