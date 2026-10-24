import { isValidClassicAddress } from "xrpl";
import { z } from "zod";
import type { Preview } from "../../preview/src/index.js";

const drops = z.string().regex(/^\d+$/, "must be a drops integer string");

export const PolicySchema = z
  .object({
    perTxCapDrops: drops,
    dailyBudgetDrops: drops,
    allowedMerchants: z.array(z.string()),
    allowedNetworks: z.array(z.string()),
    allowedAssets: z.array(z.string()),
    holdTimeoutSeconds: z.number().int().positive(),
    // v1.4. Optional so a policy file written before v1.4 still loads; the wallet fills the issuer with the hot account.
    credentialIssuer: z.string().refine(isValidClassicAddress, "must be a classic address").optional(),
    credentialType: z.string().min(1).refine((t) => Buffer.byteLength(t, "utf8") <= 64, "at most 64 bytes").default("x402-merchant"),
    // v1.6: the mandate's lifetime. Absent = no expiry; once passed, every payment is refused (policy_expired).
    expiresAt: z.iso.datetime({ offset: true }).optional(),
  })
  .strict();
export type Policy = z.infer<typeof PolicySchema>;

/** x402 v2 PaymentRequirements as the 402 sent it. Unknown keys allowed in `extra`. */
export const RequirementsSchema = z.object({
  scheme: z.string(),
  network: z.string(),
  amount: drops,
  asset: z.string(),
  payTo: z.string().min(1),
  maxTimeoutSeconds: z.number().int().positive(),
  extra: z
    .object({
      invoiceId: z.string().optional(),
      sourceTag: z.union([z.number(), z.string()]).optional(),
      destinationTag: z.union([z.number(), z.string()]).optional(),
      facilitator: z.unknown().optional(),
      issuer: z.unknown().optional(),
    })
    .passthrough()
    .optional(),
});
export type Requirements = z.infer<typeof RequirementsSchema>;

export const PayBodySchema = z.object({
  requirements: RequirementsSchema,
  // "treasury": a direct payment from the Ledger account, delegated to the hot key (no x402 facilitator).
  source: z.enum(["hot", "treasury"]).optional(),
  purpose: z.string().optional(),
  resource: z
    .object({ url: z.string().optional(), description: z.string().optional() })
    .passthrough()
    .optional(),
});
export type PayBody = z.infer<typeof PayBodySchema>;

export type Status = "auto" | "held" | "approved" | "refused" | "expired";
export type Signer = "hot" | "device" | "hot (delegated)";

export type RefuseReason =
  | "policy_expired"
  | "merchant_not_credentialed"
  | "daily_budget_exceeded"
  | "network_not_allowed"
  | "asset_not_allowed"
  | "denied_on_device"
  | "device_unavailable";

export type RequestRow = {
  id: string;
  ts: string;
  merchant: string;
  amountDrops: string;
  purpose: string;
  resourceUrl: string;
  status: Status;
  reason: string | null;
  signer: Signer | null;
  txHash: string | null;
  /** Absent = "hot" (x402). */
  source?: "hot" | "treasury";
  /** Absent = "pay". "delegate" rows are device-signed DelegateSet grants and revokes. */
  kind?: "pay" | "delegate" | "lend";
  /** v1.5: plain-English preview of the transaction the wallet built (preview/ describe()). */
  preview?: Preview;
  /** "lend" rows: the LoanSet the device approval stands for, when the desk sent its blob. */
  loanPreview?: Preview;
  /** v1.6: sha256 (uppercase hex) of policy.json as it stood when the request was decided. */
  policyHash?: string;
};

export type Decision =
  | { kind: "auto" }
  | { kind: "hold" }
  | { kind: "refuse"; reason: RefuseReason };

export type SignedTx = { blob: string; hash: string };
