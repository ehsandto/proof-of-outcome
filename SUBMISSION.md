# Portal Submission

## Title

ProofOfOutcome — Consensus Certificates for Autonomous Agent Execution

## Description

ProofOfOutcome is a reusable GenLayer primitive that certifies whether a specific autonomous-agent execution satisfied a declared outcome template. Template creators define an objective, ordered criteria and evidence policy; agents submit instance-specific claims with public HTTPS evidence. For every verification, the leader and validators independently fetch every evidence source and repeat the bounded assessment. Consensus requires exact equality of the overall outcome, every ordered criterion result, failure codes, evidence source count/statuses/fingerprint and confidence bucket. Contract code derives SUCCESS, FAILED or INCONCLUSIVE; unavailable evidence forces INCONCLUSIVE. No free-form explanation is stored or reused. Certificates are immutable by claim revision, later evidence revisions preserve history, and other contracts can use is_certified_success as a composable settlement or access gate. GenVM lint, six direct tests, static checks and exact on-chain source verification pass.

## Evidence

- Repository: https://github.com/ehsandto/proof-of-outcome
- Contract: https://explorer-studio.genlayer.com/address/0x8175264B473186ed62C6d9c48b7F3C2598543E78
- Deployment: https://explorer-studio.genlayer.com/tx/0x535585e8106bbb30eb7823b8871f20360c86ef7af9618385ccb76e082ba21e47
