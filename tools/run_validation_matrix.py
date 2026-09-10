from __future__ import annotations

from forgesense_sim.validation import run_validation_matrix


def main() -> int:
    results = run_validation_matrix()
    print(
        "scenario                 fault   warning terminal state          hard_critical result"
    )
    print("-" * 86)
    for result in results:
        state = result.terminal_state.name if result.terminal_state is not None else "-"
        print(
            f"{result.scenario:24} "
            f"{str(result.fault_start):>5} "
            f"{str(result.first_warning):>7} "
            f"{str(result.terminal_index):>8} "
            f"{state:14} "
            f"{str(result.hard_critical_at_terminal):>13} "
            f"{'PASS' if result.passed else 'FAIL'}"
        )
    failed = [result for result in results if not result.passed]
    if failed:
        for result in failed:
            print(f"FAIL {result.scenario}: {result.rationale}")
        return 1
    print(f"\nvalidation matrix PASS ({len(results)}/{len(results)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
