from __future__ import annotations

import argparse
from pathlib import Path
import sys
import threading

from forgesense_telemetry.device_stream import decode_device_line, ingest_device_packet
from forgesense_telemetry.server import TelemetryHttpServer
from forgesense_telemetry.store import TelemetryStore


def _consume_lines(lines, store: TelemetryStore, max_source_age_ms: int) -> None:
    for raw in lines:
        try:
            packet = decode_device_line(raw)
            ingest_device_packet(store, packet, max_source_age_ms=max_source_age_ms)
        except ValueError:
            continue


def _serial_lines(port: str, baud: int):
    try:
        import serial
    except ImportError as exc:
        raise SystemExit("pyserial is required for --device-port; install requirements-device.txt") from exc
    connection = serial.Serial(port, baudrate=baud, timeout=1)
    try:
        while True:
            line = connection.readline()
            if line:
                yield line
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the read-only ForgeSense monitor from a physical ESP32-S3 telemetry stream.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--device-port", help="Host serial device carrying @FS1 telemetry records, for example COM8 or /dev/ttyACM0")
    source.add_argument("--stdin", action="store_true", help="Read telemetry/log lines from standard input")
    parser.add_argument("--device-baud", type=int, default=115200)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--stale-after-ms", type=int, default=2000)
    args = parser.parse_args()

    if not 1 <= args.device_baud <= 4_000_000:
        parser.error("--device-baud must be positive and reasonable")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in 1..65535")
    if args.stale_after_ms < 1:
        parser.error("--stale-after-ms must be positive")

    store = TelemetryStore(stale_after_ms=args.stale_after_ms)
    lines = sys.stdin if args.stdin else _serial_lines(args.device_port, args.device_baud)
    reader = threading.Thread(target=_consume_lines, args=(lines, store, args.stale_after_ms), daemon=True)
    reader.start()

    dashboard_dir = Path(__file__).resolve().parents[1] / "dashboard"
    server = TelemetryHttpServer((args.host, args.port), store, dashboard_dir)
    print(f"ForgeSense physical-device monitor: http://{args.host}:{args.port}")
    print("Telemetry input is read-only; non-@FS1 console log lines are ignored.")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
