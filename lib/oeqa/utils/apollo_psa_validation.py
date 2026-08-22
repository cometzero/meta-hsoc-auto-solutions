from __future__ import annotations

import re


PSA_TOTAL_FIELDS = {
    "TESTS": "tests",
    "PASSED": "passed",
    "SIM ERROR": "sim_error",
    "FAILED": "failed",
    "SKIPPED": "skipped",
}
PSA_TOTAL_RECORD = re.compile(
    r"TOTAL[ \t]+(TESTS|PASSED|SIM ERROR|FAILED|SKIPPED)[ \t]*:[ \t]*(\d+)[ \t]*$"
)


def parse_psa_summary(output: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line.upper().startswith("TOTAL"):
            continue
        match = PSA_TOTAL_RECORD.fullmatch(line)
        if match is None:
            raise ValueError("psa_summary_invalid_total_record")
        field, raw_value = match.groups()
        key = PSA_TOTAL_FIELDS[field]
        if key in values:
            raise ValueError(f"psa_summary_duplicate_{key}")
        values[key] = int(raw_value)
    if set(values) != set(PSA_TOTAL_FIELDS.values()):
        raise ValueError("psa_summary_missing_required_totals")
    if values["tests"] <= 0:
        raise ValueError("psa_summary_zero_tests")
    if values["failed"] or values["sim_error"]:
        raise ValueError("psa_summary_failures")
    if values["passed"] + values["skipped"] != values["tests"]:
        raise ValueError("psa_summary_inconsistent_totals")
    return values
