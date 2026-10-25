from pathlib import Path


SOURCE = Path("contracts/proof_of_outcome.py").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require(SOURCE.startswith('# v0.2.0\n# { "Depends": "py-genlayer:'), "format and runner must be pinned")
require("run_nondet_unsafe" in SOURCE, "custom validator is required")
require("_reports_identical" in SOURCE, "substantive exact comparison is required")
for field in (
    'leader["criteria_results_json"] == validator["criteria_results_json"]',
    'leader["failure_codes_json"] == validator["failure_codes_json"]',
    'leader["evidence_count"] == validator["evidence_count"]',
    'leader["evidence_statuses_json"] == validator["evidence_statuses_json"]',
    'leader["evidence_fingerprint"] == validator["evidence_fingerprint"]',
):
    require(field in SOURCE, f"missing validator binding: {field}")
require("explanation=" not in SOURCE, "explanations must not enter storage")
require("summary=" not in SOURCE, "summaries must not enter storage")
print("static checks passed")
