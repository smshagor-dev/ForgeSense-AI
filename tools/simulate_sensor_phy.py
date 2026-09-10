from __future__ import annotations

import argparse
import math


def linear_calibrate(raw: int, raw_zero: int, numerator: int, denominator: int, offset: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    value = math.trunc(((raw - raw_zero) * numerator) / denominator) + offset
    return min(32767, max(-32768, value))


def rms(samples: list[int]) -> int:
    if not samples:
        raise ValueError("samples required")
    return math.isqrt(sum(x * x for x in samples) // len(samples))


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercise the vendor-neutral ForgeSense sensor PHY reference.")
    parser.add_argument("--temperature-deci-c", type=int, default=385)
    parser.add_argument("--current-raw", type=int, default=1420)
    args = parser.parse_args()

    vibration = [180, -220, 260, -200, 210, -250, 230, -190] * 8
    result = {
        "temperature_deci_c": linear_calibrate(args.temperature_deci_c, 0, 1, 1, 0),
        "current_milli_a": linear_calibrate(args.current_raw, 0, 1, 1, 0),
        "vibration_milli_g_rms": rms(vibration),
        "vibration_samples": len(vibration),
    }
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
