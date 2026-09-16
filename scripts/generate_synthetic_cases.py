"""Generate a batch of SYNTHETIC request PDFs for demos and manual testing.

These are separate from the 40 evaluation cases (different id prefix and seed).

Usage: python scripts/generate_synthetic_cases.py --count 30
"""

import argparse
import random
from pathlib import Path

from synthetic_cases import build_random_case, write_case_pdf

OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "synthetic_cases"
RANDOM_SEED = 2026


def main() -> None:
    """Write the requested number of random synthetic cases to data/synthetic_cases/."""
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument("--count", type=int, default=30)
    arguments = argument_parser.parse_args()

    random_generator = random.Random(RANDOM_SEED)
    scenario_counts: dict[str, int] = {}
    for case_number in range(1, arguments.count + 1):
        case = build_random_case(f"DEMO-{case_number:03d}", random_generator)
        write_case_pdf(case, OUTPUT_DIRECTORY)
        scenario_counts[case.scenario] = scenario_counts.get(case.scenario, 0) + 1

    print(f"Wrote {arguments.count} synthetic cases to {OUTPUT_DIRECTORY}")
    for scenario_name, count in sorted(scenario_counts.items()):
        print(f"  {scenario_name}: {count}")


if __name__ == "__main__":
    main()
