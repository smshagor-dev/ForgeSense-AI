from __future__ import annotations

import argparse
from pathlib import Path

from forgesense_telemetry.demo import start_demo_publisher
from forgesense_telemetry.server import TelemetryHttpServer
from forgesense_telemetry.store import TelemetryStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local ForgeSense monitoring dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--scenario",
        default="bearing_degradation",
        choices=("normal", "bearing_degradation", "overcurrent", "cooling_loss", "sensor_dropout"),
    )
    parser.add_argument("--interval", type=float, default=0.08)
    args = parser.parse_args()

    dashboard_dir = Path(__file__).resolve().parents[1] / "dashboard"
    store = TelemetryStore()
    start_demo_publisher(store, scenario_name=args.scenario, interval_s=args.interval)
    server = TelemetryHttpServer((args.host, args.port), store, dashboard_dir)
    print(f"ForgeSense monitoring dashboard: http://{args.host}:{args.port}")
    print("API is read-only; no actuator/control routes are exposed.")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
