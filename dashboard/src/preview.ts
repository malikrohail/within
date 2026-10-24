// The Preview module (preview/ at the repo root): plain-English cards for XRPL transactions.
import type { WalletStatus } from "./api";

export { describe, worstRisk } from "../../preview/src/index";
export type { Line, Preview, Risk } from "../../preview/src/index";

/** Same names and network the wallet passes when it builds a preview (wallet/src/server.ts previewOf). */
export function walletCtx(status: WalletStatus | null) {
  const names: Record<string, string> = {};
  if (status?.hotAccount) names[status.hotAccount] = "agent (hot key)";
  if (status?.deviceAccount) names[status.deviceAccount] = "treasury (Ledger)";
  return { names, network: "xrpl:1" };
}
