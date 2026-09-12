from __future__ import annotations

import argparse
from pathlib import Path
import sys

try:
    from commissioning.forgesense_commission.authority_transition import (
        MaintenanceAuthorityTransitionError,
        package_transition,
        verify_transition_package,
    )
except ModuleNotFoundError:
    from forgesense_commission.authority_transition import (  # type: ignore
        MaintenanceAuthorityTransitionError,
        package_transition,
        verify_transition_package,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify old/new detached signatures and package a maintenance-authority transition"
    )
    parser.add_argument("request_dir", type=Path)
    parser.add_argument("--old-signature", type=Path, required=True)
    parser.add_argument("--new-signature", type=Path, required=True)
    parser.add_argument("--old-public-key", type=Path, required=True)
    parser.add_argument("--new-public-key", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        package_transition(
            args.request_dir,
            old_signature_path=args.old_signature,
            new_signature_path=args.new_signature,
            old_public_key_path=args.old_public_key,
            new_public_key_path=args.new_public_key,
            output_dir=args.out_dir,
        )
        verified = verify_transition_package(args.out_dir)
        print(
            f"transition package verified: old={verified.old_public_key_sha256} "
            f"new={verified.new_public_key_sha256} payload={verified.payload_sha256}"
        )
        return 0
    except (MaintenanceAuthorityTransitionError, OSError, ValueError) as exc:
        print(f"maintenance-authority transition packaging failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
