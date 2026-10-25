// Read-only, independent verification of an escrow-demo proof manifest.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import { createClient } from "genlayer-js-next";
import { studioDevnet } from "genlayer-js-next/chains";
import { TransactionHashVariant } from "genlayer-js-next/types";

const file = process.argv[2];
assert.ok(file, "Usage: npm run verify:escrow -- path/to/proof.json");
const manifest = JSON.parse(await fs.readFile(file, "utf8"));
const deploymentOnly = process.argv.includes("--deployments-only");
assert.equal(manifest.chainId, 61997);
assert.ok(deploymentOnly || manifest.status !== "PARTIAL", "Live workflow is incomplete; use --deployments-only to check deployed source and receipts");
const client = createClient({ chain: studioDevnet });
assert.equal(Number(await client.getChainId()), 61997);
const sha = (text: string) => createHash("sha256").update(text).digest("hex");
for (const name of ["registry", "escrow"] as const) {
  const address = manifest[name] as `0x${string}`;
  assert.match(address, /^0x[0-9a-fA-F]{40}$/);
  const local = await fs.readFile(`contracts/${name === "registry" ? "proof_of_outcome" : "agent_escrow"}.py`, "utf8");
  assert.equal(sha(local.replace(/\r\n/g, "\n")), manifest.sourceSha256[name], "Manifest differs from checked-out source");
  assert.equal(sha(await client.getContractCode(address)), manifest.sourceSha256[name], "Onchain source differs");
}
for (const [name, item] of Object.entries(manifest.transactions) as [string, any][]) {
  if (deploymentOnly && !["deployRegistry", "deployEscrow"].includes(name)) continue;
  const receipt: any = await client.getTransaction({ hash: item.hash });
  assert.equal(receipt.statusName, "FINALIZED", name);
  assert.equal(receipt.result_name, "MAJORITY_AGREE", name);
  assert.equal(receipt.leader_only, false, name);
  assert.equal(receipt.txExecutionResultName, item.expectedError ? "FINISHED_WITH_ERROR" : "FINISHED_WITH_RETURN", name);
  if (item.expectedError) assert.ok(JSON.stringify(receipt.consensus_data?.leader_receipt).includes(item.expectedError), name);
}
if (deploymentOnly) {
  console.log(JSON.stringify({ verified: true, chainId: 61997, registry: manifest.registry,
    escrow: manifest.escrow, scope: "Two finalized deployments and matching source only; settlement workflow not verified." }, null, 2));
  process.exit(0);
}
const read = (address: `0x${string}`, functionName: string, args: any[] = []) => client.readContract({
  address, functionName, args, transactionHashVariant: TransactionHashVariant.LATEST_FINAL,
}) as Promise<any>;
const escrow = manifest.escrow as `0x${string}`, registry = manifest.registry as `0x${string}`;
const book = await read(escrow, "accounting");
assert.equal(String(book.proof_registry).toLowerCase(), registry.toLowerCase());
assert.equal(BigInt(book.funded), BigInt(book.locked) + BigInt(book.credits) + BigInt(book.payout_requested));
const success = await read(registry, "get_certificate", ["delivery-pass", 1]);
const failed = await read(registry, "get_certificate", ["delivery-fail", 1]);
assert.equal(success.outcome, "SUCCESS");
assert.equal(success.confidence_bucket, "HIGH");
assert.equal(failed.outcome, "FAILED");
assert.match(success.evidence_fingerprint, /^[0-9a-f]{64}$/);
assert.equal((await read(escrow, "get_stage", ["delivery", 0])).status, "EARNED");
assert.equal(BigInt(await read(escrow, "credit_of", [manifest.provider])), 1_000_000n);
console.log(JSON.stringify({ verified: true, chainId: 61997, registry, escrow,
  checkedTransactions: Object.keys(manifest.transactions).length,
  scope: "Finalized contract state and credits; no external EVM payout delivery claimed." }, null, 2));
