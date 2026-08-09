import fs from "node:fs";
import path from "node:path";
import { createAccount, createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";

const account = createAccount();
const client = createClient({ chain: studionet, account });
const code = fs.readFileSync(path.resolve("contracts/proof_of_outcome.py"), "utf8");
console.log(`deployer=${account.address}`);
const hash = await client.deployContract({ account, code, args: [] });
console.log(`deploymentTransaction=${hash}`);
const receipt = await client.waitForTransactionReceipt({
  hash: hash as never, status: TransactionStatus.FINALIZED, interval: 5000, retries: 180,
}) as any;
const address = receipt.data?.contract_address ?? receipt.txDataDecoded?.contractAddress;
const leaderReceipts = receipt.consensus_data?.leader_receipt ?? [];
const fatal = leaderReceipts.filter((item: any) => item.execution_result !== "SUCCESS" &&
  item.genvm_result?.error_code !== "CONSENSUS_VALIDATOR_QUORUM_REACHED");
if (!address || receipt.result_name !== "MAJORITY_AGREE" || fatal.length) {
  throw new Error(`Deployment failed: ${JSON.stringify({ address, consensus: receipt.result_name, fatal })}`);
}
console.log(JSON.stringify({
  contractAddress: address,
  deploymentTransaction: hash,
  status: receipt.status_name,
  consensus: receipt.result_name,
  contractExplorer: `https://explorer-studio.genlayer.com/address/${address}`,
  transactionExplorer: `https://explorer-studio.genlayer.com/tx/${hash}`,
}, null, 2));
