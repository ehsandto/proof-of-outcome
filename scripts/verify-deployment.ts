import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

const address = process.env.CONTRACT_ADDRESS as `0x${string}` | undefined;
const transactionHash = process.env.DEPLOY_TX as `0x${string}` | undefined;
if (!address || !transactionHash) throw new Error("Set CONTRACT_ADDRESS and DEPLOY_TX.");
const client = createClient({ chain: studionet });
const transaction = await client.getTransaction({ hash: transactionHash as never });
const [schema, deployedCode] = await Promise.all([
  client.getContractSchema(address), client.getContractCode(address),
]);
const localCode = fs.readFileSync(path.resolve("contracts/proof_of_outcome.py"), "utf8");
const sha = (value: string) => createHash("sha256").update(value.replace(/\r\n/g, "\n")).digest("hex");
if (!deployedCode || sha(deployedCode) !== sha(localCode)) throw new Error("Deployed source mismatch.");
console.log(JSON.stringify({
  status: transaction.statusName,
  consensus: (transaction as any).result_name,
  contractAddress: address,
  transactionHash,
  sourceSha256: sha(localCode),
  schemaMethods: Object.keys((schema as any).methods ?? {}),
}, null, 2));
