import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

const address = "0x8175264B473186ed62C6d9c48b7F3C2598543E78" as `0x${string}`;
const client = createClient({ chain: studionet });
const suffix = process.env.PROOF_SUFFIX ?? "1786285898766";
for (const label of ["software-delivery-4x4", "package-release-4x4"]) {
  const claimId = `${label}-claim-${suffix}`;
  const certificate = await client.readContract({ address, functionName: "get_certificate", args: [claimId, 1] });
  console.log(JSON.stringify({ label, claimId, certificate }, null, 2));
}
