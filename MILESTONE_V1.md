# Milestone v1 — Staged escrow with finalized proof gates

Baseline: [`c65c0a5`](https://github.com/ehsandto/proof-of-outcome/commit/c65c0a5819b0d7a6ce0830595be0be4d5c4c35f3).
The baseline supplied outcome certificates and a boolean success view. It did
not contain funded agreements, stage budgets, provider acceptance, payment
credits, deadline recovery or a settlement consumer.

## New workflow

1. A client creates a reusable outcome template in ProofOfOutcome. Each
   criterion is mandatory. Only that client's active templates can fund an agreement.
2. `fund_agreement(id, provider, stages_json, grace_seconds)` locks exactly the
   sum of 1–8 positive stage budgets. Each stage fixes its template, task
   reference, expected outcome, amount and increasing UTC deadline. The policy
   snapshot is hashed. There is no administrative edit or withdrawal method.
3. The assigned provider accepts the agreement. The client can cancel only
   before acceptance. Separate wallets are roles, not proof of independent humans.
4. Read `get_stage(id, index)`. The provider must use its exact `input_reference`
   and `expected_outcome` when submitting a registry claim. The reference is a
   SHA-256 commitment to a JSON tuple of escrow address, agreement ID, stage
   number and original task reference; delimiter tricks cannot alias two tasks.
5. The provider calls `bind_claim(id, claim_id, revision)` before the stage
   deadline. The registry claim must already be finalized and match the
   assigned provider and every task field. Rebinding revisions is allowed only
   before that deadline. Historical certificates remain immutable.
6. Anyone may request registry verification and call `release_stage(id)`.
   The escrow synchronously reads **LATEST_FINAL** registry state, requires the
   bound current revision, the pinned template policy, SUCCESS, HIGH confidence,
   every criterion PASS, no failure codes and every source OK. It earns the
   provider one withdrawal credit and advances exactly one stage. It does not
   run an alternative judgment or accept caller-supplied certificate JSON.
7. At `deadline + grace_seconds`, release closes and permissionless
   `refund_expired(id)` returns only the remaining unearned budget as client
   credit. The release/refund windows have no overlap. Previously earned
   provider credits are preserved. Grace is 1 hour to 7 days, fixed at funding.
8. A credit owner can call `withdraw()`. The contract debits the credit, journals
   a numbered payout request and emits a native-value external EVM message to
   that same owner. Release never automatically sends payment. Double withdrawal
   cannot emit another request from the same credit.

Accounting invariant: `funded == locked + credits + payout_requested`.
`payout_requested` means value requested for external transfer, **not confirmed
delivery**. Inspect the child EVM transaction independently. A failed child
transaction is not automatically recredited or retried: its outcome may be
ambiguous, and blindly retrying could pay twice. The current contract has no
automated payout reconciliation or recovery mechanism. Use test value only.

## Evidence integrity change

The baseline fingerprint summarized only the first/last 48 characters and length.
Two different bodies could therefore compare equal. The new registry hashes
every raw response byte and then hashes the ordered URL/status/body-digest
manifest. A same-length middle edit now makes validators disagree even when
the LLM classification stays unchanged. Evidence above 12,000 bytes or invalid
UTF-8 deterministically becomes UNAVAILABLE / INCONCLUSIVE. No prefix is judged
as if it were the entire artifact.

This is a fresh deployment. Old contracts and certificates are not upgraded;
the historical address in README and DEPLOYMENT_EVIDENCE.md remains historical.
Consumers must pin the new address and independently verify its deployed source.
SHA-256 proves content identity, not whether an evidence publisher is honest.

## Reproduce the tests

Use Python 3.12 and Node 24:

```sh
python -m venv .venv
# Activate .venv using your shell's standard activation command.
python -m pip install -r requirements.txt
npm ci
genvm-lint check contracts/proof_of_outcome.py --json
genvm-lint check contracts/agent_escrow.py --json
pytest tests/direct -q --junitxml=artifacts/escrow-tests.xml
python tools/static_checks.py
npm run typecheck
npm run demo:escrow
```

The no-flag demo prints a plan and source hashes without network writes.
For a public Studio Next run, set `EVIDENCE_COMMIT` to a full, published commit
SHA containing `evidence/escrow`, then run:

```sh
npm run demo:escrow -- --write-demo
```

The explicit write demo uses fresh in-memory keys and the Studio faucet, never
a user's funded wallet. It checks chain 61997, deploys both contracts, compares
onchain source hashes, uses immutable commit URLs and waits for finalized
MAJORITY_AGREE with successful execution. Negative transactions must finalize
with the specific expected error. A journal saves submitted hashes before
polling; an ambiguous timeout never resubmits them. Do not blindly rerun after
an interruption: inspect the saved transactions first. The ephemeral demo keys
are intentionally not recoverable, so its simulated funds are disposable.

## Test scope

The suite runs the actual registry and escrow source through `genlayer-test`
and its `glsim` multi-contract engine. It covers role checks, immutable terms,
one/eight-stage budgets, replay across stages and agreements, revision changes,
partial completion, cancellation, expiry boundaries, all-rule/source/confidence
gates, payout request idempotency and value conservation. Baseline direct tests
also rerun leader/validator comparison with matching and conflicting results.

Web and LLM responses are mocked in local tests. External EVM emission is captured
by a host adapter; it does not prove EVM delivery. The Windows fixture only fixes
an upstream open-stdin-file compatibility issue; the simulation adapter also
refreshes raw transaction time because this pinned SDK exposes time separately.
Local tests do not establish live validator consensus, network finality, security
auditing, customer adoption or production readiness.

Studio uses simulated balances and has no real EVM/ghost-contract layer. The
public demo verifies credits and cancellation, not external EVM withdrawals.
Deadline expiry is covered locally; the public demo does not fast-forward the
network clock. Both JSON evidence files explicitly identify their scenarios as
synthetic fixtures, not real customer work.

Official references: [value transfers](https://docs.genlayer.com/developers/intelligent-contracts/features/value-transfers)
and [contract interaction](https://docs.genlayer.com/developers/intelligent-contracts/features/interacting-with-intelligent-contracts).
