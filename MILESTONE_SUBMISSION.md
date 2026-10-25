# Milestone v1 submission

## Title

AgentEscrow v1: staged agreements and finalized proof gates

## Changes & Improvements

Implemented staged AgentEscrow agreements beyond the original outcome-certificate registry. Clients lock 1–8 stage budgets and immutable acceptance terms; assigned providers accept and bind exact claim revisions before deadlines. Settlement requires finalized GenLayer SUCCESS, every mandatory criterion PASS, all sources OK and HIGH confidence. Task commitments prevent cross-agreement replay. Completed stages earn provider credits; expiry refunds only unearned funds. Pull withdrawals journal payout requests. Evidence now uses full-body SHA-256 and rejects oversized or invalid UTF-8 sources. Added 80 passing tests, a reproducible demo and an independent deployment verifier. Both contracts are deployed on Studio Next (61997) with finalized majority agreement. A hosted RPC database error currently blocks the live settlement demo. Studio balances are simulated; external EVM payout delivery is not claimed.

## Evidence

- [Documented delta and exact review path](https://github.com/ehsandto/proof-of-outcome/blob/main/MILESTONE_V1.md)
- [Deployment receipts, addresses and source hashes](https://github.com/ehsandto/proof-of-outcome/blob/main/deployments/escrow-studio-next.json)
- [Local test results and scope](https://github.com/ehsandto/proof-of-outcome/blob/main/evidence/milestone-v1/local-validation.json)
- [New escrow contract](https://explorer-studio-dev.genlayer.com/address/0xed0D38AC2472d3D732D0D1c220F0B7f12b9Eb1fd)

Change type: new contract functionality / security improvement, using the
closest available form option. This file is draft copy; no portal form was submitted.
