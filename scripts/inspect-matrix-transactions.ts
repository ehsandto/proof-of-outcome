import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

const client = createClient({ chain: studionet });
const hashes = process.argv.slice(2);
for (const hash of hashes) {
  const tx = await client.getTransaction({ hash: hash as never });
  const data = tx as any;
  if (process.env.FULL_TRANSACTION === "1") {
    console.log(JSON.stringify(data, null, 2));
    continue;
  }
  const receipt = data.consensus_data?.leader_receipt ?? [];
  console.log(JSON.stringify({
    hash,
    status: data.statusName,
    consensus: data.result_name,
    decoded: data.txDataDecoded,
    executions: receipt.map((item: any) => ({ result: item.execution_result,
      code: item.genvm_result?.error_code ?? null, resultData: item.result ?? null })),
  }, null, 2));
}
