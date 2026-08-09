import { createAccount, createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";

const address = "0x8175264B473186ed62C6d9c48b7F3C2598543E78" as `0x${string}`;
const commit = process.env.EVIDENCE_COMMIT;
if (!commit) throw new Error("Set EVIDENCE_COMMIT to the public Git commit containing evidence.");
const account = createAccount();
const client = createClient({ chain: studionet, account });
const suffix = Date.now();
const rawBase = `https://raw.githubusercontent.com/ehsandto/proof-of-outcome/${commit}/evidence`;

const matrices = [
  {
    label: "software-delivery-4x4",
    title: "Software delivery outcome matrix",
    objective: "Verify that commit def456 is a safe, documented software delivery satisfying all four declared controls.",
    criteria: [
      "All 184 required tests passed with zero failures",
      "The public API has no removed or renamed operations and no breaking change",
      "Critical and high vulnerability counts did not increase from zero",
      "The changelog and public documentation were updated",
    ],
    policy: "Require all four commit-pinned evidence sources. Each criterion needs affirmative machine-readable evidence; any absent or contradictory source is not success.",
    reference: "repository-upgrade:abc123..def456",
    expected: "Safe software delivery with tests, compatibility, security, and documentation controls satisfied.",
    urls: ["ci.json", "api-compatibility.json", "security.json", "documentation.json"].map((name) => `${rawBase}/software-delivery/${name}`),
  },
  {
    label: "package-release-4x4",
    title: "Package release integrity matrix",
    objective: "Verify that package release 4.2.0 is published, source-bound, provenance-matched, and license-compliant.",
    criteria: [
      "Version 4.2.0 is published by the package registry",
      "Repository tag v4.2.0 matches the manifest and its commit is signed",
      "Build provenance matches artifact digest sha256:matrix-demo-420 and verifies the builder",
      "The declared MIT license is in the allowed license set",
    ],
    policy: "Require registry, repository, provenance, and license evidence. All sources and all four criteria must affirmatively pass.",
    reference: "proof-matrix-demo@4.2.0",
    expected: "A published release with coherent source, provenance, artifact, and license evidence.",
    urls: ["registry.json", "repository.json", "provenance.json", "license.json"].map((name) => `${rawBase}/package-release/${name}`),
  },
];

async function write(functionName: string, args: any[]) {
  const hash = await client.writeContract({ address, functionName, args, account, value: 0n });
  console.log(`${functionName}=${hash}`);
  const receipt = await client.waitForTransactionReceipt({
    hash: hash as never, status: TransactionStatus.FINALIZED, interval: 5000, retries: 180,
  }) as any;
  const executions = (receipt.consensus_data?.leader_receipt ?? []).map((item: any) => ({
    result: item.execution_result, code: item.genvm_result?.error_code ?? null,
  }));
  const fatal = executions.filter((item: any) => item.result !== "SUCCESS" &&
    item.code !== "CONSENSUS_VALIDATOR_QUORUM_REACHED");
  if (receipt.result_name !== "MAJORITY_AGREE" || fatal.length) {
    throw new Error(`${functionName} failed: ${JSON.stringify({ hash, consensus: receipt.result_name, executions })}`);
  }
  return { hash, explorer: `https://explorer-studio.genlayer.com/tx/${hash}`,
    status: receipt.status_name, consensus: receipt.result_name };
}

const proofs: unknown[] = [];
for (const matrix of matrices) {
  const templateId = `${matrix.label}-template-${suffix}`;
  const claimId = `${matrix.label}-claim-${suffix}`;
  const templateTx = await write("create_template", [templateId, matrix.title, matrix.objective,
    JSON.stringify(matrix.criteria), matrix.policy]);
  const claimTx = await write("submit_claim", [claimId, templateId, matrix.reference,
    matrix.expected, JSON.stringify(matrix.urls)]);
  const verifyTx = await write("verify_claim", [claimId]);
  const certificate = await client.readContract({ address, functionName: "get_certificate", args: [claimId, 1] });
  proofs.push({ label: matrix.label, dimensions: "4 criteria x 4 sources", templateId, claimId,
    templateTx, claimTx, verifyTx, certificate });
}
console.log(JSON.stringify({ contractAddress: address, evidenceCommit: commit, proofCount: proofs.length, proofs }, null, 2));
