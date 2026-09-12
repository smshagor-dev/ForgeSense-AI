from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "forgesense.firmware_build_provenance.v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a hash-bound ForgeSense firmware build provenance manifest")
    parser.add_argument("--repository-commit", required=True)
    parser.add_argument("--idf-version", required=True)
    parser.add_argument("--sdkconfig", type=Path, required=True)
    parser.add_argument("--application", type=Path, required=True)
    parser.add_argument("--bootloader", type=Path, required=True)
    parser.add_argument("--partition-table", type=Path, required=True)
    parser.add_argument("--signing-public-key", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    commit = args.repository_commit.lower()
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise SystemExit("repository commit must be a full 40-hex SHA")
    files = {
        "sdkconfig": args.sdkconfig,
        "application": args.application,
        "bootloader": args.bootloader,
        "partition_table": args.partition_table,
    }
    for label, path in files.items():
        if not path.is_file():
            raise SystemExit(f"{label} file not found: {path}")
    public_key_fingerprint = None
    if args.signing_public_key is not None:
        if not args.signing_public_key.is_file():
            raise SystemExit(f"signing public key file not found: {args.signing_public_key}")
        public_key_fingerprint = sha256_file(args.signing_public_key)

    manifest = {
        "schema": SCHEMA,
        "repository_commit": commit,
        "esp_idf_version": args.idf_version,
        "artifacts": {
            label: {"path": str(path), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
            for label, path in files.items()
        },
        "signing_public_key_sha256": public_key_fingerprint,
        "authority": {
            "build_provenance_only": True,
            "installed_image_attestation": False,
            "private_key_accessed": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
