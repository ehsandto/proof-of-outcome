"""Real registry + escrow in glsim; web/LLM and external EVM are test doubles.

The EVM hook models message emission, not delivery/finality on a real chain.
"""
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json

import pytest
from glsim.engine import SimEngine
from glsim.state import StateStore


CLIENT = "0x" + "11" * 20
PROVIDER = "0x" + "22" * 20
STRANGER = "0x" + "33" * 20
NOW = 1792886400
DEADLINE = NOW + 7200
GRACE = 3600


class World:
    def __init__(self):
        self.engine = SimEngine(StateStore(chain_id=61999, seed="escrow-tests"))
        self.engine.activate()
        self.vm = self.engine.vm
        self.warp(NOW)
        self.registry, _ = self.engine.deploy("contracts/proof_of_outcome.py", sender=CLIENT)
        self.escrow, _ = self.engine.deploy("contracts/agent_escrow.py", args=[self.registry], sender=CLIENT)
        self.messages = []
        self.final_reads = []
        self.certificate_override = None
        original_hook = self.vm._gl_call_hook

        def host(vm, request):
            if "CallContract" in request:
                self.final_reads.append(request["CallContract"]["state"])
                if self.certificate_override is not None and request["CallContract"]["calldata"]["method"] == "get_certificate":
                    from genlayer.py import calldata
                    return b"\x00" + calldata.encode(self.certificate_override)
            if "EthSend" in request:
                self.messages.append(request["EthSend"])
                return b""  # The EVM message API returns bytes, not calldata.
            return original_hook(vm, request)

        self.vm._gl_call_hook = host
        self.call(self.registry, "create_template", ["delivery", "Delivery", "Deliver the requested build.",
                  '["Tests pass","Documentation is present"]', "Require both controls."], CLIENT)
        self.mock_report()

    def warp(self, seconds):
        self.vm.warp(datetime.fromtimestamp(seconds, timezone.utc).isoformat())

    def call(self, address, method, args=None, sender=CLIENT, value=0):
        self.vm.value = value
        # This pinned SDK exposes datetime in message_raw. glsim refreshes
        # MessageType but not message_raw between in-process transactions.
        import genlayer.gl as gl
        gl.message_raw["datetime"] = self.vm._datetime
        try:
            result = self.engine.call_method(address, method, args or [], sender=sender)
            return asdict(result) if is_dataclass(result) else result
        finally:
            self.vm.value = 0

    def esc(self, method, args=None, sender=CLIENT, value=0):
        return self.call(self.escrow, method, args, sender, value)

    def mock_report(self, results=None, confidence="HIGH", status=200):
        self.vm.clear_mocks()
        self.vm.mock_web(r"example\.com/proof", {"status": status, "body": "Tests pass; documentation is present."})
        self.vm.mock_llm(r"independently verifying", json.dumps({
            "criteria_results": results or ["PASS", "PASS"], "confidence_bucket": confidence,
        }))

    def fund(self, aid="job", count=2, items=None, value=None, grace=GRACE, provider=PROVIDER):
        items = items if items is not None else [
            {"template_id": "delivery", "input_reference": "repository:abc", "expected_outcome": "Documented tested build",
             "amount": (index + 1) * 10, "deadline": DEADLINE + index * 7200}
            for index in range(count)
        ]
        budget = sum(item.get("amount", 0) for item in items) if value is None else value
        self.esc("fund_agreement", [aid, provider, json.dumps(items), grace], value=budget)
        self.vm.deal(self.escrow, self.vm._balances.get(bytes.fromhex(self.escrow[2:]), 0) + budget)
        return items

    def accept(self, aid="job"):
        self.esc("accept_agreement", [aid], PROVIDER)

    def claim(self, aid="job", cid="proof", index=0, verify=True, **overrides):
        stage = self.esc("get_stage", [aid, index])
        args = {"template_id": stage["template_id"], "input_reference": stage["input_reference"],
                "expected_outcome": stage["expected_outcome"]}
        args.update(overrides)
        self.call(self.registry, "submit_claim", [cid, args["template_id"], args["input_reference"],
                  args["expected_outcome"], '["https://example.com/proof"]'], PROVIDER)
        if verify:
            self.call(self.registry, "verify_claim", [cid], STRANGER)

    def ready(self, count=2):
        self.fund(count=count)
        self.accept()
        self.claim()
        self.esc("bind_claim", ["job", "proof", 1], PROVIDER)

    def invariant(self):
        book = self.esc("accounting")
        assert book["funded"] == book["locked"] + book["credits"] + book["payout_requested"]
        assert all(book[field] >= 0 for field in ("funded", "locked", "credits", "payout_requested"))


@pytest.fixture
def world():
    instance = World()
    yield instance
    instance.engine.deactivate()


def test_two_stage_real_registry_consumption(world):
    world.ready()
    world.esc("release_stage", ["job"], STRANGER)
    assert world.esc("credit_of", [PROVIDER]) == 10
    assert world.esc("get_stage", ["job", 0])["status"] == "EARNED"
    world.claim(cid="proof-2", index=1)
    world.esc("bind_claim", ["job", "proof-2", 1], PROVIDER)
    world.esc("release_stage", ["job"], STRANGER)
    assert world.esc("get_agreement", ["job"])["status"] == "COMPLETED"
    assert world.esc("credit_of", [PROVIDER]) == 30
    assert world.final_reads and set(world.final_reads) == {1}
    assert not world.messages  # Release is a credit, not a claimed transfer.
    world.invariant()


@pytest.mark.parametrize("results,confidence,status", [
    (["PASS", "FAIL"], "HIGH", 200), (["PASS", "UNKNOWN"], "HIGH", 200),
    (["PASS", "PASS"], "MEDIUM", 200), (["PASS", "PASS"], "LOW", 200),
    (["PASS", "PASS"], "HIGH", 404),
])
def test_nonpayable_judgments_never_release(world, results, confidence, status):
    world.mock_report(results, confidence, status)
    world.ready()
    with pytest.raises(Exception, match="SUCCESS|all rules"):
        world.esc("release_stage", ["job"])
    assert world.esc("credit_of", [PROVIDER]) == 0
    assert world.esc("accounting")["locked"] == 30
    world.invariant()


@pytest.mark.parametrize("field,value", [("input_reference", "unrelated"), ("expected_outcome", "An easier task")])
def test_provider_cannot_rewrite_requester_terms(world, field, value):
    world.fund()
    world.accept()
    world.claim(**{field: value})
    with pytest.raises(Exception, match="claim must match"):
        world.esc("bind_claim", ["job", "proof", 1], PROVIDER)


def test_wrong_provider_claim_rejected(world):
    world.fund()
    world.accept()
    stage = world.esc("get_stage", ["job", 0])
    world.call(world.registry, "submit_claim", ["other", "delivery", stage["input_reference"],
               stage["expected_outcome"], '["https://example.com/proof"]'], STRANGER)
    with pytest.raises(Exception, match="claim must match"):
        world.esc("bind_claim", ["job", "other", 1], PROVIDER)


def test_cross_agreement_and_stage_replay_rejected(world):
    world.ready()
    world.fund(aid="other")
    world.accept("other")
    with pytest.raises(Exception, match="claim must match"):
        world.esc("bind_claim", ["other", "proof", 1], PROVIDER)
    world.esc("release_stage", ["job"])
    with pytest.raises(Exception, match="claim must match"):
        world.esc("bind_claim", ["job", "proof", 1], PROVIDER)
    world.invariant()


def test_domain_reference_has_no_delimiter_collision(world):
    world.fund(aid="a:0:repository")
    items = [{"template_id": "delivery", "input_reference": "repository:0:repository:abc",
              "expected_outcome": "Documented tested build", "amount": 10, "deadline": DEADLINE}]
    world.fund(aid="a", items=items)
    assert world.esc("get_stage", ["a:0:repository", 0])["input_reference"] != world.esc("get_stage", ["a", 0])["input_reference"]


def test_revision_rebinding_and_historical_certificate(world):
    world.ready(count=1)
    world.call(world.registry, "submit_revision", ["proof", '["https://example.com/proof"]'], PROVIDER)
    with pytest.raises(Exception, match="current revision"):
        world.esc("release_stage", ["job"])
    world.esc("bind_claim", ["job", "proof", 2], PROVIDER)
    with pytest.raises(Exception):
        world.esc("release_stage", ["job"])
    world.call(world.registry, "verify_claim", ["proof"], STRANGER)
    world.esc("release_stage", ["job"])
    assert world.call(world.registry, "get_certificate", ["proof", 1])["outcome"] == "SUCCESS"
    assert world.esc("get_stage", ["job", 0])["revision"] == 2
    world.invariant()


@pytest.mark.parametrize("sender", [CLIENT, STRANGER])
def test_only_assigned_provider_accepts_and_binds(world, sender):
    world.fund()
    with pytest.raises(Exception, match="provider required"):
        world.esc("accept_agreement", ["job"], sender)
    world.accept()
    world.claim()
    with pytest.raises(Exception, match="provider required"):
        world.esc("bind_claim", ["job", "proof", 1], sender)


def test_cancel_only_before_acceptance(world):
    world.fund()
    with pytest.raises(Exception, match="client"):
        world.esc("cancel_unaccepted", ["job"], STRANGER)
    world.accept()
    with pytest.raises(Exception, match="unaccepted"):
        world.esc("cancel_unaccepted", ["job"])
    world.invariant()


def test_cancel_refunds_once(world):
    world.fund()
    world.esc("cancel_unaccepted", ["job"])
    assert world.esc("credit_of", [CLIENT]) == 30
    with pytest.raises(Exception, match="unaccepted"):
        world.esc("cancel_unaccepted", ["job"])
    with pytest.raises(Exception, match="refundable"):
        world.esc("refund_expired", ["job"], STRANGER)
    world.invariant()


def test_partial_delivery_refunds_only_remaining_budget(world):
    world.ready()
    world.esc("release_stage", ["job"])
    world.warp(DEADLINE + 7200 + GRACE)
    world.esc("refund_expired", ["job"], STRANGER)
    assert world.esc("credit_of", [PROVIDER]) == 10
    assert world.esc("credit_of", [CLIENT]) == 20
    assert world.esc("get_agreement", ["job"])["remaining"] == 0
    with pytest.raises(Exception, match="not active"):
        world.esc("release_stage", ["job"])
    world.invariant()


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_evidence_submission_deadline_boundary(world, offset):
    world.fund(count=1)
    world.accept()
    world.claim()
    world.warp(DEADLINE + offset)
    if offset < 0:
        world.esc("bind_claim", ["job", "proof", 1], PROVIDER)
    else:
        with pytest.raises(Exception, match="submission deadline"):
            world.esc("bind_claim", ["job", "proof", 1], PROVIDER)


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_release_refund_windows_do_not_overlap(world, offset):
    world.ready(count=1)
    world.warp(DEADLINE + GRACE + offset)
    if offset < 0:
        with pytest.raises(Exception, match="still open"):
            world.esc("refund_expired", ["job"])
        world.esc("release_stage", ["job"])
    else:
        with pytest.raises(Exception, match="settlement window"):
            world.esc("release_stage", ["job"])
        world.esc("refund_expired", ["job"], STRANGER)
    world.invariant()


def test_deactivating_template_does_not_cancel_funded_terms(world):
    world.ready(count=1)
    world.call(world.registry, "set_template_active", ["delivery", False])
    world.esc("release_stage", ["job"])
    world.invariant()


def test_withdraw_emits_once_to_credit_owner(world):
    world.ready(count=1)
    world.esc("release_stage", ["job"])
    with pytest.raises(Exception, match="withdrawal credit"):
        world.esc("withdraw", sender=STRANGER)
    world.esc("withdraw", sender=PROVIDER)
    assert len(world.messages) == 1
    assert str(world.messages[0]["address"]).lower() == PROVIDER.lower()
    assert world.messages[0]["value"] == 10
    assert world.messages[0]["calldata"] == b""
    assert world.esc("credit_of", [PROVIDER]) == 0
    assert world.esc("get_payout_request", [1])["amount"] == 10
    with pytest.raises(Exception, match="withdrawal credit"):
        world.esc("withdraw", sender=PROVIDER)
    assert len(world.messages) == 1
    world.invariant()


def test_insufficient_host_balance_preserves_credit(world):
    world.ready(count=1)
    world.esc("release_stage", ["job"])
    world.vm.deal(world.escrow, 0)
    with pytest.raises(Exception, match="withdrawal credit"):
        world.esc("withdraw", sender=PROVIDER)
    assert world.esc("credit_of", [PROVIDER]) == 10
    assert not world.messages
    world.invariant()


@pytest.mark.parametrize("count", [1, 3, 8])
def test_conservation_across_every_stage_and_withdrawal(world, count):
    world.fund(count=count)
    world.accept()
    for index in range(count):
        world.claim(cid=f"proof-{index}", index=index)
        world.esc("bind_claim", ["job", f"proof-{index}", 1], PROVIDER)
        world.esc("release_stage", ["job"], STRANGER)
        world.invariant()
    world.esc("withdraw", sender=PROVIDER)
    world.invariant()
    assert world.esc("accounting")["payout_requested"] == sum((index + 1) * 10 for index in range(count))


@pytest.mark.parametrize("overrides,error", [
    ({"amount": 0}, "invalid amount"), ({"amount": -1}, "invalid amount"),
    ({"amount": True}, "invalid amount"), ({"amount": 1.5}, "invalid amount"),
    ({"amount": 2**256}, "invalid amount"), ({"deadline": NOW}, "deadlines"),
    ({"deadline": NOW + 31536001}, "deadlines"), ({"deadline": True}, "deadlines"),
    ({"input_reference": " two  spaces "}, "canonical"), ({"expected_outcome": ""}, "canonical"),
    ({"unexpected": "x"}, "stage fields"),
])
def test_invalid_stage_rejected_before_storage(world, overrides, error):
    item = {"template_id": "delivery", "input_reference": "repo", "expected_outcome": "Build",
            "amount": 10, "deadline": DEADLINE}
    item.update(overrides)
    with pytest.raises(Exception, match=error):
        world.fund(items=[item], value=10)
    assert world.esc("accounting")["funded"] == 0


@pytest.mark.parametrize("grace", [3599, 604801, -1])
def test_invalid_grace(world, grace):
    with pytest.raises(Exception, match="grace"):
        world.fund(grace=grace)


@pytest.mark.parametrize("value", [0, 29, 31])
def test_deposit_must_exactly_cover_budget(world, value):
    with pytest.raises(Exception, match="stage budget"):
        world.fund(value=value)
    assert world.esc("accounting")["locked"] == 0


@pytest.mark.parametrize("count", [0, 9])
def test_stage_count_bounds(world, count):
    with pytest.raises(Exception, match="one to eight"):
        world.fund(count=count)


@pytest.mark.parametrize("provider", [CLIENT, "0x" + "00" * 20])
def test_provider_must_be_separate_nonzero_address(world, provider):
    with pytest.raises(Exception, match="distinct nonzero"):
        world.fund(provider=provider)


def test_duplicate_agreement_rejected(world):
    world.fund()
    with pytest.raises(Exception, match="agreement exists"):
        world.fund()
    world.invariant()


def test_template_must_belong_to_client(world):
    world.call(world.registry, "create_template", ["other", "Other", "Agent controls this.", '["Pass"]', "Evidence"], PROVIDER)
    items = [{"template_id": "other", "input_reference": "repo", "expected_outcome": "Build", "amount": 10, "deadline": DEADLINE}]
    with pytest.raises(Exception, match="client-owned"):
        world.fund(items=items)


def test_acceptance_deadline_and_unbound_release(world):
    world.fund()
    world.warp(DEADLINE)
    with pytest.raises(Exception, match="acceptance deadline"):
        world.accept()
    world.warp(NOW)
    world.accept()
    with pytest.raises(Exception, match="bound claim"):
        world.esc("release_stage", ["job"])


@pytest.mark.parametrize("index", [-1, 2, 100])
def test_invalid_stage_index(world, index):
    world.fund()
    with pytest.raises(Exception, match="stage index"):
        world.esc("get_stage", ["job", index])


@pytest.mark.parametrize("field,value", [
    ("criteria_results_json", '["PASS","FAIL"]'), ("criteria_results_json", '["PASS","UNKNOWN"]'),
    ("criteria_results_json", '["PASS"]'), ("failure_codes_json", '["criterion-2"]'),
    ("evidence_statuses_json", '["UNAVAILABLE"]'), ("evidence_statuses_json", '[]'),
    ("evidence_count", 2), ("evidence_fingerprint", ""), ("confidence_bucket", "MEDIUM"),
    ("revision", 2), ("claim_id", "unrelated"), ("outcome", "FAILED"),
])
def test_inconsistent_success_certificate_cannot_earn_credit(world, field, value):
    world.ready(count=1)
    certificate = world.call(world.registry, "get_certificate", ["proof", 1])
    certificate[field] = value
    world.certificate_override = certificate
    with pytest.raises(Exception, match="required"):
        world.esc("release_stage", ["job"])
    assert world.esc("credit_of", [PROVIDER]) == 0
    assert world.esc("accounting")["locked"] == 10
    world.invariant()
