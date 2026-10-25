# ProofOfOutcome

ProofOfOutcome is a standalone GenLayer primitive that creates consensus-backed,
revisioned certificates proving whether a specific autonomous-agent execution
satisfied a reusable outcome template.

It is not an identity, reputation, oracle, or generic AI-judgment contract. A
certificate is instance-specific: it binds one claim revision to every declared
criterion and every fetched evidence source.

## Consensus invariant

The leader and every validator independently fetch all evidence URLs and repeat
the bounded assessment. Consensus requires exact equality of:

- overall outcome (`SUCCESS`, `FAILED`, or `INCONCLUSIVE`);
- every ordered criterion result;
- canonical failure codes;
- evidence source count and every source status;
- the combined evidence fingerprint; and
- confidence bucket.

The outcome is derived by contract code from criterion and source results. No
free-form explanation is stored, compared loosely, or reused in future decisions.
Unavailable evidence deterministically forces `INCONCLUSIVE`.

## Milestone v1: staged AgentEscrow agreements

The new [AgentEscrow contract](contracts/agent_escrow.py) consumes finalized
ProofOfOutcome certificates to release staged native-GEN withdrawal credits.
Clients fund immutable acceptance terms; assigned providers accept them and bind
evidence revisions before deadlines. Failed, inconclusive, stale-revision and
replayed certificates cannot release a stage. Expiry returns only unearned funds.

Evidence fingerprints now use SHA-256 over full response bytes, URLs and status
codes. Oversized or invalid UTF-8 evidence is unavailable, never silently truncated.

See [MILESTONE_V1.md](MILESTONE_V1.md) for the baseline, trust model, exact review
path, test scope and deployment evidence. Studio balances are simulated;
external EVM payout delivery is a separate transaction and is not claimed by a
withdrawal credit or an emitted payout request.

## Historical StudioNet deployment (pre-milestone source)

- Contract: [`0x8175264B473186ed62C6d9c48b7F3C2598543E78`](https://explorer-studio.genlayer.com/address/0x8175264B473186ed62C6d9c48b7F3C2598543E78)
- Deployment: [`0x535585...21e47`](https://explorer-studio.genlayer.com/tx/0x535585e8106bbb30eb7823b8871f20360c86ef7af9618385ccb76e082ba21e47)
- Consensus: `FINALIZED / MAJORITY_AGREE` (3 agree, 0 disagree)
- Exact deployed-source SHA-256: `afd82e6a571d83c712fabb52e76394169850ee9ceceba2b01639be677561e25f`

## State and composition

- Creators publish reusable, deactivatable templates.
- Agents submit claims containing immutable objective references and HTTPS evidence.
- Verification writes an immutable certificate keyed by claim and revision.
- Agents can submit later evidence revisions without overwriting earlier certificates.
- Consumers use `is_certified_success(claim_id, revision)` as an on-chain gate.

Two live 4×4 outcome matrices (software delivery and package-release integrity)
are documented with all template, claim, certificate, and immutable evidence
links in [PROOF_MATRICES.md](PROOF_MATRICES.md).

## Validation

```bash
genvm-lint check contracts/proof_of_outcome.py --json
genvm-lint check contracts/agent_escrow.py --json
pytest tests/direct -q
python tools/static_checks.py
npm ci
npm run typecheck
npm run demo:escrow
```
