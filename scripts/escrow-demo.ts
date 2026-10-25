// Fresh faucet-only Studio accounts. Keys remain in memory and are never saved.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import { createAccount, createClient } from "genlayer-js-next";
import { studioDevnet } from "genlayer-js-next/chains";
import { TransactionHashVariant } from "genlayer-js-next/types";

const source = {
  registry: (await fs.readFile("contracts/proof_of_outcome.py", "utf8")).replace(/\r\n/g, "\n"),
  escrow: (await fs.readFile("contracts/agent_escrow.py", "utf8")).replace(/\r\n/g, "\n"),
};
const sha = (text: string) => createHash("sha256").update(text).digest("hex");
const sourceSha256 = { registry: sha(source.registry), escrow: sha(source.escrow) };
const writeDemo = process.argv.includes("--write-demo");
if (!writeDemo) {
  console.log(JSON.stringify({ chainId: studioDevnet.id, sourceSha256,
    mode: "plan; no network writes", command: "npm run demo:escrow -- --write-demo",
    required: "EVIDENCE_COMMIT must be a published 40-character commit SHA",
    scope: "Studio simulated balances; payout credits only. External EVM delivery is not demonstrated." }, null, 2));
  process.exit(0);
}
const commit = process.env.EVIDENCE_COMMIT;
assert.ok(commit && /^[a-f0-9]{40}$/.test(commit), "Set EVIDENCE_COMMIT to a published 40-character SHA");
const output = process.env.ESCROW_DEMO_OUTPUT ?? `artifacts/escrow-${Date.now()}`;
await fs.mkdir(output, { recursive: true });
const serialize = (value: unknown) => JSON.stringify(value, (_, item) => typeof item === "bigint" ? String(item) : item, 2) + "\n";
const save = (name: string, value: unknown) => fs.writeFile(`${output}/${name}.json`, serialize(value));
const clientAccount = createAccount(), providerAccount = createAccount(), keeperAccount = createAccount();
const client = createClient({ chain: studioDevnet, account: clientAccount });
const provider = createClient({ chain: studioDevnet, account: providerAccount });
const keeper = createClient({ chain: studioDevnet, account: keeperAccount });
assert.equal(Number(await client.getChainId()), 61997);
for (const account of [clientAccount, providerAccount, keeperAccount]) {
  await client.request({ method: "sim_fundAccount" as never, params: [account.address, 10_000_000_000_000_000_000] as never });
}
const journal: any = { chainId: 61997, evidenceCommit: commit, sourceSha256, sourceEncoding: "UTF-8 LF",
  client: clientAccount.address, provider: providerAccount.address, keeper: keeperAccount.address,
  transactions: {}, scope: "Synthetic demo evidence and Studio simulated balances. No external EVM payout or real agent delivery claimed." };
await save("journal", journal);
async function fees() {
  const quote = await client.estimateTransactionFees({ leaderTimeunitsAllocation: 100n,
    validatorTimeunitsAllocation: 200n, rotations: [3n], appealRounds: 0n, totalMessageFees: 0n });
  assert.ok(quote.feeValue <= 110_000_000_000_000_000n, "Protocol fee exceeds demo cap");
  return { distribution: quote.distribution, feeValue: quote.feeValue };
}
async function step(name: string, submit: () => Promise<unknown>, expectedError?: string) {
  const hash = await submit();
  journal.transactions[name] = { hash, submittedAt: new Date().toISOString() };
  await save("journal", journal);
  console.log(serialize({ step: name, hash }).trim());
  // Poll the same hash. An ambiguous timeout never resubmits a transaction.
  const receipt: any = await client.waitForTransactionReceipt({ hash: hash as never,
    waitUntil: "finalized", fullTransaction: true, interval: 3000, retries: 120 });
  await save(name, receipt);
  assert.equal(receipt.statusName, "FINALIZED");
  assert.equal(receipt.leader_only, false);
  assert.equal(receipt.result_name, "MAJORITY_AGREE");
  assert.equal(receipt.txExecutionResultName, expectedError ? "FINISHED_WITH_ERROR" : "FINISHED_WITH_RETURN");
  if (expectedError) assert.ok(JSON.stringify(receipt.consensus_data?.leader_receipt).includes(expectedError), "Wrong rejection");
  journal.transactions[name] = { hash, status: receipt.statusName, consensus: receipt.result_name,
    execution: receipt.txExecutionResultName, ...(expectedError ? { expectedError } : {}) };
  await save("journal", journal);
  console.log(serialize({ step: name, execution: receipt.txExecutionResultName }).trim());
  return receipt;
}
const registryDeployment = await step("deployRegistry", async () => client.deployContract({
  code: source.registry, args: [], leaderOnly: false, fees: await fees(),
}));
const registry = (registryDeployment.data?.contract_address ?? registryDeployment.txDataDecoded?.contractAddress) as `0x${string}`;
assert.ok(registry);
assert.equal(sha(await client.getContractCode(registry)), sourceSha256.registry);
journal.registry = registry;
await save("journal", journal);
const escrowDeployment = await step("deployEscrow", async () => client.deployContract({
  code: source.escrow, args: [registry], leaderOnly: false, fees: await fees(),
}));
const escrow = (escrowDeployment.data?.contract_address ?? escrowDeployment.txDataDecoded?.contractAddress) as `0x${string}`;
assert.ok(escrow);
assert.equal(sha(await client.getContractCode(escrow)), sourceSha256.escrow);
journal.escrow = escrow;
await save("journal", journal);
const read = (address: `0x${string}`, functionName: string, args: any[] = []) => client.readContract({
  address, functionName, args, transactionHashVariant: TransactionHashVariant.LATEST_FINAL,
}) as Promise<any>;
// Keep fee quotes explicit for every write, including negative transactions.
async function send(signer: typeof client, address: `0x${string}`, functionName: string, args: any[], value = 0n) {
  return signer.writeContract({ address, functionName, args, value, leaderOnly: false, fees: await fees() });
}
const tid = "escrow-demo-policy";
await step("createPolicy", () => send(client, registry, "create_template", [tid, "Synthetic delivery acceptance",
  "Evaluate the synthetic scenario described in the evidence, not the existence of this test fixture.",
  JSON.stringify(["The scenario reports that all required checks passed with zero failures.",
    "The scenario says the delivered report includes both reproduction steps and limitations."]),
  "Both mandatory criteria need affirmative support. A failing check is FAIL; unavailable evidence is UNKNOWN."]));
const deadline = Math.floor(Date.now() / 1000) + 86400;
const stages = [0, 1].map(index => ({ template_id: tid, input_reference: `demo-stage-${index}`,
  expected_outcome: "A passing synthetic delivery with reproducible, documented results",
  amount: 1_000_000, deadline: deadline + index * 86400 }));
await step("fundAgreement", () => send(client, escrow, "fund_agreement", ["delivery", providerAccount.address, JSON.stringify(stages), 3600], 2_000_000n));
await step("acceptAgreement", () => send(provider, escrow, "accept_agreement", ["delivery"]));
await step("rejectClientCancellation", () => send(client, escrow, "cancel_unaccepted", ["delivery"]), "unaccepted agreement");
const raw = `https://raw.githubusercontent.com/ehsandto/proof-of-outcome/${commit}/evidence/escrow`;
for (const [index, fixture] of ["pass", "fail"].entries()) {
  const stage = await read(escrow, "get_stage", ["delivery", index]);
  const claimId = `delivery-${fixture}`;
  await step(`submit-${fixture}`, () => send(provider, registry, "submit_claim", [claimId, tid,
    stage.input_reference, stage.expected_outcome, JSON.stringify([`${raw}/${fixture}.json`])]));
  await step(`bind-${fixture}`, () => send(provider, escrow, "bind_claim", ["delivery", claimId, 1]));
  await step(`verify-${fixture}`, () => send(keeper, registry, "verify_claim", [claimId]));
  const certificate = await read(registry, "get_certificate", [claimId, 1]);
  assert.equal(certificate.outcome, index === 0 ? "SUCCESS" : "FAILED");
  if (index === 0) assert.equal(certificate.confidence_bucket, "HIGH");
  await save(`certificate-${fixture}`, certificate);
  await step(`release-${fixture}`, () => send(keeper, escrow, "release_stage", ["delivery"]), index === 1 ? "matching SUCCESS" : undefined);
  assert.equal(BigInt(await read(escrow, "credit_of", [providerAccount.address])), 1_000_000n);
  if (index === 0) await step("rejectReleaseReplay", () => send(keeper, escrow, "release_stage", ["delivery"]), "bound claim");
}
await step("fundCancellable", () => send(client, escrow, "fund_agreement", ["cancel-demo", providerAccount.address, JSON.stringify([stages[0]]), 3600], 1_000_000n));
await step("cancelUnaccepted", () => send(client, escrow, "cancel_unaccepted", ["cancel-demo"]));
assert.equal(BigInt(await read(escrow, "credit_of", [clientAccount.address])), 1_000_000n);
const accounting = await read(escrow, "accounting");
assert.equal(BigInt(accounting.funded), BigInt(accounting.locked) + BigInt(accounting.credits) + BigInt(accounting.payout_requested));
assert.equal(BigInt(accounting.payout_requested), 0n);
const proof = { ...journal, completedAt: new Date().toISOString(), accounting,
  agreement: await read(escrow, "get_agreement", ["delivery"]),
  stages: await Promise.all([0, 1].map(index => read(escrow, "get_stage", ["delivery", index]))),
  providerCredit: await read(escrow, "credit_of", [providerAccount.address]),
  clientCredit: await read(escrow, "credit_of", [clientAccount.address]),
  notDemonstrated: ["External EVM payout delivery", "Deadline refund on a public network", "Real customer usage"],
};
await save("proof", proof);
console.log(serialize({ registry, escrow, proof: `${output}/proof.json`, transactions: Object.keys(journal.transactions).length }).trim());
