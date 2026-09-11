from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from .core import (
    apply_observation_to_record,
    apply_smoke_to_record,
    observe_production_stream,
    run_smoke_commissioning,
)


def _serial_port(name: str, baud: int, timeout: float):
    try:
        import serial  # type: ignore
    except ImportError as exc:
        raise SystemExit("pyserial is required for physical commissioning: install the commissioning optional dependency") from exc
    return serial.Serial(name, baudrate=baud, timeout=timeout, write_timeout=timeout)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _record_from_template(args: argparse.Namespace) -> dict:
    record = deepcopy(_load_json(Path(args.record_template)))
    record["record_id"] = args.record_id
    record["timestamp_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    record["operator"] = args.operator
    record["repository_commit"] = args.repository_commit
    record["board"]["fpga_board_revision"] = args.fpga_board_revision
    record["board"]["sensor_board_revision"] = args.sensor_board_revision
    record["image"]["top"] = args.image_top
    record["image"]["artifact_sha256"] = args.artifact_sha256
    return record


def _add_record_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--record-template", default="hardware/bringup/bench_record_template_v1.json")
    parser.add_argument("--record-out")
    parser.add_argument("--record-id", default="COMMISSION-UNSET")
    parser.add_argument("--operator", default="UNSET")
    parser.add_argument("--repository-commit", default="0" * 40)
    parser.add_argument("--artifact-sha256", default="0" * 64)
    parser.add_argument("--fpga-board-revision", default="UNSET")
    parser.add_argument("--sensor-board-revision", default="UNSET")
    parser.add_argument("--image-top", default="forgesense_tang_nano_9k_smoke_top")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ForgeSense physical commissioning utility")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=0.05)
    sub = parser.add_subparsers(dest="command", required=True)

    smoke = sub.add_parser("smoke", help="verify smoke heartbeat and stop-and-wait UART echo")
    smoke.add_argument("--heartbeats", type=int, default=2)
    smoke.add_argument("--heartbeat-timeout", type=float, default=3.0)
    smoke.add_argument("--echo-timeout", type=float, default=0.5)
    smoke.add_argument("--echo-bytes", default="A6,3C,81,00,FE")
    smoke.add_argument("--report-out")
    _add_record_args(smoke)

    observe = sub.add_parser("observe", help="decode production STATUS and sensor frames without sending control commands")
    observe.add_argument("--duration", type=float, default=3.0)
    observe.add_argument("--report-out")
    _add_record_args(observe)
    observe.set_defaults(image_top="forgesense_tang_nano_9k_top")
    return parser


def _parse_echo_bytes(value: str) -> bytes:
    items = [item.strip() for item in value.split(",") if item.strip()]
    try:
        result = bytes(int(item, 16) for item in items)
    except ValueError as exc:
        raise SystemExit("--echo-bytes must be comma-separated hex bytes, e.g. A6,3C,81") from exc
    if not result:
        raise SystemExit("--echo-bytes must contain at least one byte")
    return result


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    serial_port = _serial_port(args.port, args.baud, args.timeout)
    try:
        if hasattr(serial_port, "reset_input_buffer"):
            serial_port.reset_input_buffer()
        if args.command == "smoke":
            metrics = run_smoke_commissioning(
                serial_port,
                required_heartbeats=args.heartbeats,
                heartbeat_timeout_s=args.heartbeat_timeout,
                echo_bytes=_parse_echo_bytes(args.echo_bytes),
                echo_timeout_s=args.echo_timeout,
            )
            report = {"mode": "smoke", "result": metrics.as_dict()}
            record = apply_smoke_to_record(_record_from_template(args), metrics)
            exit_code = 0 if metrics.heartbeat_pass and metrics.echo_pass else 2
        else:
            observer = observe_production_stream(serial_port, duration_s=args.duration)
            report = {"mode": "observe", "result": observer.as_dict()}
            record = apply_observation_to_record(_record_from_template(args), observer)
            status = observer.as_dict()["status"]
            exit_code = 0 if status and observer.status_frames > 0 and observer.sensor_frames > 0 else 2

        rendered = json.dumps(report, indent=2)
        print(rendered)
        if args.report_out:
            _save_json(Path(args.report_out), report)
        if args.record_out:
            _save_json(Path(args.record_out), record)
        return exit_code
    finally:
        serial_port.close()


if __name__ == "__main__":
    sys.exit(main())
