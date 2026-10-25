# v0.2.0
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from genlayer.py.public_abi import StorageType
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json


@gl.evm.contract_interface
class Recipient:
    class View:
        pass

    class Write:
        pass


@allow_storage
@dataclass
class Agreement:
    client: Address
    provider: Address
    status: str
    stage_count: u32
    next_stage: u32
    remaining: u256
    grace_seconds: u32


@allow_storage
@dataclass
class Stage:
    template_id: str
    template_hash: str
    task_reference: str
    input_reference: str
    expected_outcome: str
    amount: u256
    deadline: u64
    claim_id: str
    revision: u32
    status: str
    evidence_fingerprint: str


@allow_storage
@dataclass
class PayoutRequest:
    recipient: Address
    amount: u256


class AgentEscrow(gl.Contract):
    """Staged native-GEN escrow consuming a fixed ProofOfOutcome deployment.

    Release earns a withdrawal credit. Withdraw emits an external transfer;
    its downstream execution must be checked separately from this state.
    """

    proof_registry: Address
    agreements: TreeMap[str, Agreement]
    agreement_exists: TreeMap[str, bool]
    stages: TreeMap[str, Stage]
    credits: TreeMap[Address, u256]
    payout_requests: TreeMap[str, PayoutRequest]
    total_funded: u256
    total_locked: u256
    total_credits: u256
    total_payout_requested: u256
    payout_count: u64

    def __init__(self, proof_registry: str) -> None:
        registry = Address(proof_registry)
        if registry == Address("0x0000000000000000000000000000000000000000"):
            raise gl.vm.UserError("EXPECTED: zero registry")
        self.proof_registry = registry
        self.total_funded = u256(0)
        self.total_locked = u256(0)
        self.total_credits = u256(0)
        self.total_payout_requested = u256(0)
        self.payout_count = u64(0)

    @gl.public.write.payable
    def fund_agreement(self, agreement_id: str, provider: str, stages_json: str, grace_seconds: int) -> None:
        aid = self._id(agreement_id)
        if self.agreement_exists.get(aid, False):
            raise gl.vm.UserError("EXPECTED: agreement exists")
        agent = Address(provider)
        if agent == gl.message.sender_address or agent == Address("0x0000000000000000000000000000000000000000"):
            raise gl.vm.UserError("EXPECTED: distinct nonzero provider required")
        if grace_seconds < 3600 or grace_seconds > 604800:
            raise gl.vm.UserError("EXPECTED: grace must be 3600..604800 seconds")
        if len(stages_json) > 24000:
            raise gl.vm.UserError("EXPECTED: stages too large")
        try:
            items = json.loads(stages_json)
        except Exception:
            raise gl.vm.UserError("EXPECTED: invalid stages JSON")
        if not isinstance(items, list) or not 1 <= len(items) <= 8:
            raise gl.vm.UserError("EXPECTED: one to eight stages required")
        total = 0
        previous_deadline = self._now()
        prepared = []
        for index, item in enumerate(items):
            if not isinstance(item, dict) or set(item) != {"template_id", "input_reference", "expected_outcome", "amount", "deadline"}:
                raise gl.vm.UserError("EXPECTED: invalid stage fields")
            amount = item["amount"]
            deadline = item["deadline"]
            if type(amount) is not int or amount <= 0 or amount >= 2**256:
                raise gl.vm.UserError("EXPECTED: invalid amount")
            if type(deadline) is not int or not previous_deadline < deadline <= self._now() + 31536000:
                raise gl.vm.UserError("EXPECTED: deadlines must increase within one year")
            tid = self._id(item["template_id"])
            template = self._registry().get_template(tid)
            if template["creator"] != gl.message.sender_address or not template["active"]:
                raise gl.vm.UserError("EXPECTED: active client-owned template required")
            reference = self._text(item["input_reference"], 1200)
            # Domain separation prevents a certificate being reused for another
            # escrow, agreement or stage, even if the task text is identical.
            scope = [str(gl.message.contract_address), aid, index, reference]
            bound_reference = "escrow-sha256:" + hashlib.sha256(json.dumps(scope, separators=(",", ":")).encode()).hexdigest()
            prepared.append(Stage(
                template_id=tid, template_hash=self._template_hash(template),
                task_reference=reference, input_reference=bound_reference,
                expected_outcome=self._text(item["expected_outcome"], 2400),
                amount=u256(amount), deadline=u64(deadline), claim_id="", revision=u32(0),
                status="PENDING", evidence_fingerprint="",
            ))
            total += amount
            previous_deadline = deadline
        if total >= 2**256 or gl.message.value != total:
            raise gl.vm.UserError("EXPECTED: value must equal stage budget")
        # Finish all validation before writing any agreement state.
        for index, stage in enumerate(prepared):
            self.stages[self._key(aid, index)] = stage
        self.agreements[aid] = Agreement(
            client=gl.message.sender_address, provider=agent, status="FUNDED",
            stage_count=u32(len(items)), next_stage=u32(0), remaining=u256(total), grace_seconds=u32(grace_seconds),
        )
        self.agreement_exists[aid] = True
        self.total_funded += u256(total)
        self.total_locked += u256(total)

    @gl.public.write
    def accept_agreement(self, agreement_id: str) -> None:
        aid = self._id(agreement_id)
        agreement = self._agreement(aid)
        if gl.message.sender_address != agreement.provider or agreement.status != "FUNDED":
            raise gl.vm.UserError("EXPECTED: funded agreement provider required")
        if self._now() >= self.stages[self._key(aid, 0)].deadline:
            raise gl.vm.UserError("EXPECTED: acceptance deadline passed")
        agreement.status = "ACTIVE"
        self.agreements[aid] = agreement

    @gl.public.write
    def bind_claim(self, agreement_id: str, claim_id: str, revision: int) -> None:
        aid = self._id(agreement_id)
        agreement = self._agreement(aid)
        if agreement.status != "ACTIVE" or gl.message.sender_address != agreement.provider:
            raise gl.vm.UserError("EXPECTED: active agreement provider required")
        key = self._key(aid, agreement.next_stage)
        stage = self.stages[key]
        if self._now() >= stage.deadline:
            raise gl.vm.UserError("EXPECTED: evidence submission deadline passed")
        cid = self._id(claim_id)
        claim = self._registry().get_claim(cid)
        self._check_claim(agreement, stage, claim, revision)
        stage.claim_id = cid
        stage.revision = u32(revision)
        self.stages[key] = stage

    @gl.public.write
    def release_stage(self, agreement_id: str) -> None:
        aid = self._id(agreement_id)
        agreement = self._agreement(aid)
        if agreement.status != "ACTIVE":
            raise gl.vm.UserError("EXPECTED: agreement not active")
        key = self._key(aid, agreement.next_stage)
        stage = self.stages[key]
        if not stage.claim_id or self._now() >= stage.deadline + agreement.grace_seconds:
            raise gl.vm.UserError("EXPECTED: bound claim within settlement window required")
        registry = self._registry()
        claim = registry.get_claim(stage.claim_id)
        self._check_claim(agreement, stage, claim, stage.revision)
        template = registry.get_template(stage.template_id)
        if self._template_hash(template) != stage.template_hash:
            raise gl.vm.UserError("EXPECTED: template policy changed")
        cert = registry.get_certificate(stage.claim_id, stage.revision)
        if cert["claim_id"] != stage.claim_id or cert["revision"] != stage.revision or cert["outcome"] != "SUCCESS":
            raise gl.vm.UserError("EXPECTED: matching SUCCESS certificate required")
        results = json.loads(cert["criteria_results_json"])
        statuses = json.loads(cert["evidence_statuses_json"])
        if (claim["status"] != "SUCCESS" or not isinstance(results, list)
                or len(results) != len(json.loads(template["criteria_json"])) or not results
                or any(result != "PASS" for result in results)
                or cert["failure_codes_json"] != "[]" or cert["confidence_bucket"] != "HIGH"
                or not isinstance(statuses, list) or not 1 <= len(statuses) <= 6
                or len(statuses) != cert["evidence_count"] or any(status != "OK" for status in statuses)
                or not cert["evidence_fingerprint"]):
            raise gl.vm.UserError("EXPECTED: all rules, sources and HIGH confidence required")
        stage.status = "EARNED"
        stage.evidence_fingerprint = cert["evidence_fingerprint"]
        agreement.remaining -= stage.amount
        agreement.next_stage += u32(1)
        if agreement.next_stage == agreement.stage_count:
            agreement.status = "COMPLETED"
        self.stages[key] = stage
        self.agreements[aid] = agreement
        self.total_locked -= stage.amount
        self._credit(agreement.provider, stage.amount)

    @gl.public.write
    def cancel_unaccepted(self, agreement_id: str) -> None:
        aid = self._id(agreement_id)
        agreement = self._agreement(aid)
        if agreement.status != "FUNDED" or agreement.client != gl.message.sender_address:
            raise gl.vm.UserError("EXPECTED: client of unaccepted agreement required")
        self._refund(aid, agreement)

    @gl.public.write
    def refund_expired(self, agreement_id: str) -> None:
        aid = self._id(agreement_id)
        agreement = self._agreement(aid)
        if agreement.status not in ("FUNDED", "ACTIVE"):
            raise gl.vm.UserError("EXPECTED: refundable agreement required")
        stage = self.stages[self._key(aid, agreement.next_stage)]
        if self._now() < stage.deadline + agreement.grace_seconds:
            raise gl.vm.UserError("EXPECTED: settlement window still open")
        self._refund(aid, agreement)

    @gl.public.write
    def withdraw(self) -> None:
        recipient = gl.message.sender_address
        amount = self.credits.get(recipient, u256(0))
        if amount == 0 or self.balance < amount:
            raise gl.vm.UserError("EXPECTED: funded withdrawal credit required")
        # Effects before asynchronous interaction. A request is not a receipt:
        # never auto-recredit or retry a failed external transfer.
        self.credits[recipient] = u256(0)
        self.total_credits -= amount
        self.total_payout_requested += amount
        self.payout_count += u64(1)
        self.payout_requests[str(self.payout_count)] = PayoutRequest(recipient=recipient, amount=amount)
        Recipient(recipient).emit_transfer(value=amount)

    @gl.public.view
    def get_agreement(self, agreement_id: str) -> Agreement:
        return self._agreement(self._id(agreement_id))

    @gl.public.view
    def get_stage(self, agreement_id: str, index: int) -> Stage:
        aid = self._id(agreement_id)
        agreement = self._agreement(aid)
        if index < 0 or index >= agreement.stage_count:
            raise gl.vm.UserError("EXPECTED: invalid stage index")
        return self.stages[self._key(aid, index)]

    @gl.public.view
    def credit_of(self, account: str) -> u256:
        return self.credits.get(Address(account), u256(0))

    @gl.public.view
    def get_payout_request(self, nonce: int) -> PayoutRequest:
        if nonce < 1 or nonce > self.payout_count:
            raise gl.vm.UserError("EXPECTED: unknown payout request")
        return self.payout_requests[str(nonce)]

    @gl.public.view
    def accounting(self) -> dict:
        return {"funded": int(self.total_funded), "locked": int(self.total_locked),
                "credits": int(self.total_credits), "payout_requested": int(self.total_payout_requested),
                "payout_count": int(self.payout_count), "proof_registry": self.proof_registry}

    def _registry(self):
        # Never release against optimistic/accepted-only certificate state.
        return gl.get_contract_at(self.proof_registry).view(state=StorageType.LATEST_FINAL)

    def _check_claim(self, agreement: Agreement, stage: Stage, claim: dict, revision: int) -> None:
        if (revision < 1 or revision >= 2**32 or claim["revision"] != revision
                or claim["agent"] != agreement.provider or claim["template_id"] != stage.template_id
                or claim["input_reference"] != stage.input_reference
                or claim["expected_outcome"] != stage.expected_outcome):
            raise gl.vm.UserError("EXPECTED: claim must match provider, task, template and current revision")

    def _template_hash(self, template: dict) -> str:
        # Active is an admission switch, not a retroactive cancellation switch.
        policy = [str(template["creator"]), template["title"], template["objective"],
                  template["criteria_json"], template["evidence_policy"]]
        return hashlib.sha256(json.dumps(policy, separators=(",", ":")).encode()).hexdigest()

    def _credit(self, recipient: Address, amount: u256) -> None:
        self.credits[recipient] = self.credits.get(recipient, u256(0)) + amount
        self.total_credits += amount

    def _refund(self, aid: str, agreement: Agreement) -> None:
        amount = agreement.remaining
        for index in range(int(agreement.next_stage), int(agreement.stage_count)):
            key = self._key(aid, index)
            stage = self.stages[key]
            stage.status = "REFUNDED"
            self.stages[key] = stage
        agreement.remaining = u256(0)
        agreement.status = "REFUNDED"
        self.agreements[aid] = agreement
        self.total_locked -= amount
        self._credit(agreement.client, amount)

    def _agreement(self, aid: str) -> Agreement:
        if not self.agreement_exists.get(aid, False):
            raise gl.vm.UserError("EXPECTED: unknown agreement")
        return self.agreements[aid]

    def _now(self) -> int:
        return int(datetime.fromisoformat(gl.message_raw["datetime"].replace("Z", "+00:00")).timestamp())

    def _key(self, aid: str, index: int) -> str:
        return aid + "#" + str(index)

    def _id(self, value: str) -> str:
        if not isinstance(value, str) or not value or len(value) > 96 or value != value.strip():
            raise gl.vm.UserError("EXPECTED: invalid identifier")
        return value

    def _text(self, value: str, maximum: int) -> str:
        if not isinstance(value, str) or not value or len(value) > maximum or value != " ".join(value.split()):
            raise gl.vm.UserError("EXPECTED: canonical nonempty task text required")
        return value
