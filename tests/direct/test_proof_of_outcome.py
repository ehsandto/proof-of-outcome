import json
import pytest


CONTRACT = "contracts/proof_of_outcome.py"


def create_template(contract):
    contract.create_template(
        "software-upgrade-v1",
        "Safe software upgrade",
        "Upgrade a repository without breaking its declared guarantees.",
        json.dumps(["All required tests pass", "No breaking API change", "Changelog is updated"]),
        "Use public CI, API-diff, and repository evidence. Every criterion needs direct evidence.",
    )


def submit_claim(contract):
    contract.submit_claim(
        "upgrade-123",
        "software-upgrade-v1",
        "before=abc123;after=def456",
        "A safe dependency upgrade",
        json.dumps(["https://example.com/ci", "https://example.com/diff"]),
    )


def passing_report():
    return json.dumps({
        "criteria_results": ["PASS", "PASS", "PASS"],
        "failure_codes": [],
        "confidence_bucket": "HIGH",
        "explanation": "ignored and never stored",
    })


def mock_success(direct_vm):
    direct_vm.mock_web(r"example\.com/ci", {"status": 200, "body": "All required tests passed. Changelog updated."})
    direct_vm.mock_web(r"example\.com/diff", {"status": 200, "body": "API diff: no removed or renamed public operations."})
    direct_vm.mock_llm(r"independently verifying", passing_report())


def test_template_and_claim_state(direct_deploy):
    contract = direct_deploy(CONTRACT)
    create_template(contract)
    submit_claim(contract)
    assert contract.get_template("software-upgrade-v1").active is True
    assert contract.get_claim("upgrade-123").status == "SUBMITTED"
    assert contract.counts() == "templates=1;claims=1;certificates=0"


def test_success_certificate_binds_all_evidence_fields(direct_vm, direct_deploy):
    mock_success(direct_vm)
    contract = direct_deploy(CONTRACT)
    create_template(contract)
    submit_claim(contract)
    contract.verify_claim("upgrade-123")
    cert = contract.get_certificate("upgrade-123", 1)
    assert cert.outcome == "SUCCESS"
    assert cert.criteria_results_json == '["PASS","PASS","PASS"]'
    assert cert.failure_codes_json == "[]"
    assert cert.evidence_count == 2
    assert cert.evidence_statuses_json == '["OK","OK"]'
    assert "example" not in cert.evidence_fingerprint
    assert cert.confidence_bucket == "HIGH"
    assert not hasattr(cert, "explanation")
    assert contract.is_certified_success("upgrade-123", 1) is True
    assert direct_vm.run_validator() is True


def test_validator_rejects_conflicting_criterion(direct_vm, direct_deploy):
    mock_success(direct_vm)
    contract = direct_deploy(CONTRACT)
    create_template(contract)
    submit_claim(contract)
    contract.verify_claim("upgrade-123")
    direct_vm.clear_mocks()
    direct_vm.mock_web(r"example\.com/ci", {"status": 200, "body": "All required tests passed. Changelog updated."})
    direct_vm.mock_web(r"example\.com/diff", {"status": 200, "body": "API diff: breaking endpoint removal."})
    direct_vm.mock_llm(r"independently verifying", json.dumps({
        "criteria_results": ["PASS", "FAIL", "PASS"],
        "failure_codes": ["criterion-2"],
        "confidence_bucket": "HIGH",
    }))
    assert direct_vm.run_validator() is False


def test_unavailable_evidence_forces_inconclusive(direct_vm, direct_deploy):
    direct_vm.mock_web(r"example\.com/ci", {"status": 404, "body": "not found"})
    direct_vm.mock_web(r"example\.com/diff", {"status": 200, "body": "No breaking API change."})
    direct_vm.mock_llm(r"independently verifying", passing_report())
    contract = direct_deploy(CONTRACT)
    create_template(contract)
    submit_claim(contract)
    contract.verify_claim("upgrade-123")
    cert = contract.get_certificate("upgrade-123", 1)
    assert cert.outcome == "INCONCLUSIVE"
    assert cert.confidence_bucket == "LOW"
    assert cert.evidence_statuses_json == '["UNAVAILABLE","OK"]'


def test_revision_preserves_old_certificate(direct_vm, direct_deploy):
    mock_success(direct_vm)
    contract = direct_deploy(CONTRACT)
    create_template(contract)
    submit_claim(contract)
    contract.verify_claim("upgrade-123")
    contract.submit_revision("upgrade-123", json.dumps(["https://example.com/ci", "https://example.com/diff"]))
    assert contract.get_claim("upgrade-123").revision == 2
    assert contract.get_certificate("upgrade-123", 1).outcome == "SUCCESS"


def test_access_control_and_input_validation(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT)
    create_template(contract)
    with direct_vm.prank(direct_bob):
        with direct_vm.expect_revert("EXPECTED: only template creator can modify"):
            contract.set_template_active("software-upgrade-v1", False)
    with direct_vm.expect_revert("EXPECTED: evidence URLs must use https"):
        contract.submit_claim("bad", "software-upgrade-v1", "x", "y", '["http://localhost/private"]')


def test_full_body_hash_rejects_same_edges_different_middle_in_validator(direct_vm, direct_deploy):
    mock_success(direct_vm)
    first = "A" * 60 + "tests passed" + "Z" * 60
    second = "A" * 60 + "tests failed" + "Z" * 60
    direct_vm.clear_mocks()
    direct_vm.mock_web(r"example\.com/ci", {"status": 200, "body": first})
    direct_vm.mock_web(r"example\.com/diff", {"status": 200, "body": "Stable API"})
    direct_vm.mock_llm(r"independently verifying", passing_report())
    contract = direct_deploy(CONTRACT)
    create_template(contract)
    submit_claim(contract)
    contract.verify_claim("upgrade-123")
    assert len(contract.get_certificate("upgrade-123", 1).evidence_fingerprint) == 64
    direct_vm.clear_mocks()
    direct_vm.mock_web(r"example\.com/ci", {"status": 200, "body": second})
    direct_vm.mock_web(r"example\.com/diff", {"status": 200, "body": "Stable API"})
    direct_vm.mock_llm(r"independently verifying", passing_report())
    assert direct_vm.run_validator() is False


@pytest.mark.parametrize("body", ["a" * 12001, "é" * 6001, b"\xff\xfe", " "])
def test_incomplete_or_invalid_evidence_forces_inconclusive(direct_vm, direct_deploy, body):
    direct_vm.mock_web(r"example\.com/ci", {"status": 200, "body": body})
    direct_vm.mock_web(r"example\.com/diff", {"status": 200, "body": "Stable API"})
    direct_vm.mock_llm(r"independently verifying", passing_report())
    contract = direct_deploy(CONTRACT)
    create_template(contract)
    submit_claim(contract)
    contract.verify_claim("upgrade-123")
    assert contract.get_certificate("upgrade-123", 1).outcome == "INCONCLUSIVE"


def test_exact_evidence_byte_limit_is_accepted(direct_vm, direct_deploy):
    direct_vm.mock_web(r"example\.com/ci", {"status": 200, "body": "a" * 12000})
    direct_vm.mock_web(r"example\.com/diff", {"status": 200, "body": "Stable API"})
    direct_vm.mock_llm(r"independently verifying", passing_report())
    contract = direct_deploy(CONTRACT)
    create_template(contract)
    submit_claim(contract)
    contract.verify_claim("upgrade-123")
    assert contract.get_certificate("upgrade-123", 1).outcome == "SUCCESS"
