from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

try:
    from commissioning.forgesense_commission.provisioning import MaintenanceProvisioningError
    from commissioning.forgesense_commission.signed_provisioning import (
        AUTHORIZATION_REQUEST_SCHEMA,
        AUTHORIZATION_SCHEMA,
        public_key_der,
        verify_signature_openssl,
    )
except ModuleNotFoundError:
    from forgesense_commission.provisioning import MaintenanceProvisioningError  # type: ignore
    from forgesense_commission.signed_provisioning import (  # type: ignore
        AUTHORIZATION_REQUEST_SCHEMA,
        AUTHORIZATION_SCHEMA,
        public_key_der,
        verify_signature_openssl,
    )


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MaintenanceProvisioningError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MaintenanceProvisioningError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MaintenanceProvisioningError(f"{label} must contain a JSON object")
    return value


def _json_bytes(data: dict) -> bytes:
    return (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_authorization(
    request_dir: Path,
    *,
    signature_path: Path,
    public_key_path: Path,
) -> dict[str, bytes]:
    request_dir = request_dir.resolve()
    request = _load_json(request_dir / "authorization-request.json", "authorization request")
    if request.get("schema") != AUTHORIZATION_REQUEST_SCHEMA:
        raise MaintenanceProvisioningError("unsupported maintenance authorization request schema")
    try:
        payload = (request_dir / "authorization-payload.bin").read_bytes()
        signature_der = signature_path.read_bytes()
    except FileNotFoundError as exc:
        raise MaintenanceProvisioningError(f"authorization input file not found: {exc.filename}") from exc

    payload_sha256 = _sha256_bytes(payload)
    if request.get("payload_sha256") != payload_sha256:
        raise MaintenanceProvisioningError("authorization request payload SHA-256 mismatch")
    if request.get("signature_format") != "ECDSA-P256-SHA256-DER":
        raise MaintenanceProvisioningError("authorization request signature format is unsupported")

    key_fingerprint = verify_signature_openssl(
        public_key_path=public_key_path,
        payload=payload,
        signature_der=signature_der,
    )
    der = public_key_der(public_key_path)
    if _sha256_bytes(der) != key_fingerprint:
        raise MaintenanceProvisioningError("maintenance authority public-key fingerprint is unstable")

    package = {
        "schema": AUTHORIZATION_SCHEMA,
        "signature_format": request["signature_format"],
        "device_id": request["device_id"],
        "expected_installed_sequence": request["expected_installed_sequence"],
        "candidate_sequence": request["candidate_sequence"],
        "artifact_root_sha256": request["artifact_root_sha256"],
        "record_sha256": request["record_sha256"],
        "payload_sha256": payload_sha256,
        "signature_sha256": _sha256_bytes(signature_der),
        "authority_public_key_sha256": key_fingerprint,
        "authority": {
            "external_signature_required": True,
            "signature_verified": True,
            "private_key_accessed_by_tool": False,
            "automatic_provisioning": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
        "verification_boundary": (
            "OpenSSL verified the detached ECDSA P-256/SHA-256 signature against the supplied public key. "
            "This package contains no private key and does not itself provision a device."
        ),
    }
    return {
        "authorization.json": _json_bytes(package),
        "authorization-signature.der": signature_der,
        "authority-public-key.der.hex": (der.hex() + "\n").encode("ascii"),
    }


def publish_atomic(out_dir: Path, artifacts: dict[str, bytes]) -> None:
    out_dir = out_dir.resolve()
    if out_dir.exists():
        raise MaintenanceProvisioningError(f"authorization output already exists: {out_dir}")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=out_dir.parent))
    try:
        for name, content in artifacts.items():
            (staging / name).write_bytes(content)
        staging.rename(out_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify and package an external ForgeSense calibration maintenance signature"
    )
    parser.add_argument("request_dir", type=Path)
    parser.add_argument("--signature", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        publish_atomic(
            args.out_dir,
            build_authorization(
                args.request_dir,
                signature_path=args.signature,
                public_key_path=args.public_key,
            ),
        )
        return 0
    except MaintenanceProvisioningError as exc:
        print(f"maintenance authorization packaging failed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
