from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def require_keys(value: dict, keys: list[str], context: str) -> None:
    for key in keys:
        if key not in value:
            raise ValueError(f"{context}: missing required field {key!r}")


def validate(record_path: Path, schema_path: Path) -> None:
    record = json.loads(record_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    if record.get("schema") != schema["record_schema"]:
        raise ValueError("record schema identifier mismatch")

    require_keys(record, schema["required_fields"], "record")
    require_keys(record["board"], schema["board_required_fields"], "board")
    require_keys(record["image"], schema["image_required_fields"], "image")

    if not HEX40.fullmatch(str(record["repository_commit"])):
        raise ValueError("repository_commit must be a full 40-hex commit SHA")
    if not HEX64.fullmatch(str(record["image"]["artifact_sha256"])):
        raise ValueError("image.artifact_sha256 must be a 64-hex SHA-256")

    if record["overall_result"] not in schema["overall_result_values"]:
        raise ValueError("unsupported overall_result")

    if not record["instruments"]:
        raise ValueError("at least one instrument entry is required")
    for index, instrument in enumerate(record["instruments"]):
        require_keys(instrument, schema["instrument_required_fields"], f"instrument[{index}]")

    if not record["supply"]:
        raise ValueError("at least one supply entry is required")
    for index, supply in enumerate(record["supply"]):
        require_keys(supply, schema["supply_required_fields"], f"supply[{index}]")

    if not record["checks"]:
        raise ValueError("at least one check entry is required")

    seen_ids: set[str] = set()
    failures = 0
    for index, check in enumerate(record["checks"]):
        require_keys(check, schema["check_required_fields"], f"check[{index}]")
        check_id = str(check["check_id"])
        if check_id in seen_ids:
            raise ValueError(f"duplicate check_id {check_id!r}")
        seen_ids.add(check_id)
        if check["result"] not in schema["check_result_values"]:
            raise ValueError(f"{check_id}: unsupported result")
        if check["result"] == "FAIL":
            failures += 1

        evidence = check["evidence"]
        if not isinstance(evidence, list):
            raise ValueError(f"{check_id}: evidence must be a list")
        for evidence_index, item in enumerate(evidence):
            require_keys(item, schema["evidence_fields"], f"{check_id}.evidence[{evidence_index}]")
            if not HEX64.fullmatch(str(item["sha256"])):
                raise ValueError(f"{check_id}: evidence SHA-256 must be 64 hex characters")

    if record["overall_result"] == "PASS":
        if failures:
            raise ValueError("PASS record contains one or more FAIL checks")
        if any(check["result"] != "PASS" for check in record["checks"]):
            raise ValueError("PASS record contains a check that is not PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a ForgeSense physical bench record")
    parser.add_argument("record", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("hardware/bringup/bench_record_schema_v1.json"),
    )
    args = parser.parse_args()

    validate(args.record, args.schema)
    print(f"bench_record_validation PASS: {args.record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
