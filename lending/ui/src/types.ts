// Desk response shapes, from lending/INTERFACES.md §3-§5. Amounts are drop strings, times unix seconds.

export type Rule = { rule: string; value: unknown; points: number };
export type SubScore = { score: number; rules: Rule[] };

export type Breakdown = {
  total: number;
  weights: { ledger: number; bank: number; declared: number };
  ledger: SubScore;
  bank: SubScore | null;
  declared: SubScore;
  capped: "past_default" | null;
};

export type LedgerEvidence = {
  accountExists: boolean;
  accountAgeLedgers: number;
  inboundPaymentCount: number;
  inboundVolumeDrops: string;
  distinctPayers: number;
  topPayerSharePct: number;
  activeDays: number;
  activeLoans: number;
  loanDebtDrops: string; // TotalValueOutstanding of open loans
  loanPrincipalDrops?: string; // PrincipalOutstanding of open loans (missing on records stored before it existed)
  pastDefaults: number;
  hasAcceptedCredential: boolean;
  sampleTxHashes: string[];
  x402IncomeDrops?: string; // Missing on records stored before it existed.
  x402Payments?: number;
  x402Payers?: number;
  otherInboundDrops?: string;
  credentialIssuer?: string; // set only when the broker's kyb-borrower Credential counts
  credentialType?: string; // "kyb-borrower"
  memoDatedPayments?: number; // payments dated by their invoice memo (missing on records stored before it existed)
  ledgerActiveDays?: number; // active days by ledger close date, memos ignored
};

export type BankEvidence = {
  connected: boolean;
  institution: string;
  days: number;
  avgMonthlyInflowUsd: number;
  avgBalanceUsd: number;
  inflowOutflowRatio: number;
  nsfCount: number;
};

export type Evidence = {
  borrower: string;
  asOf: number;
  windowDays: number;
  ledger: LedgerEvidence;
  bank: BankEvidence | null;
  declared: { purpose: string; principalDrops: string; termSeconds: number; existingDebtDrops: string };
};

export type RequestStatus = "auto" | "held" | "approved" | "denied" | "refused" | "expired" | "failed";

// Working capital (INTERFACES §8): a LoanSet, then a borrower-only all-or-nothing Batch of two Payments.
export type BatchLeg = {
  index: number;
  type: string;
  account: string;
  destination: string | null;
  amountDrops: string | null;
  hash: string;
  result: string; // tesSUCCESS | not_applied (rolled back) | not_validated | other engine code
};

export type BatchInfo = {
  supplier: string;
  supplierDrops: string;
  feeDrops: string;
  invoice: string;
  hash: string | null;
  engineResult: string | null;
  legs: BatchLeg[];
};

export type LoanRequest = {
  id: string;
  kind?: "loan" | "working_capital"; // missing = plain loan
  batch?: BatchInfo;
  ts: number;
  borrower: string;
  principalDrops: string;
  termSeconds: number;
  purpose: string;
  evidence: Evidence | Record<string, never>;
  breakdown: Breakdown | Record<string, never>;
  score: number | null;
  decision: "auto" | "hold" | "refuse" | null;
  status: RequestStatus;
  reason: string | null;
  loanId: string | null;
  txHash: string | null;
  engineResult: string | null;
  decidedBy: "policy" | "human" | "ledger" | "timeout" | null; // ledger: approved by a Ledger-signed testnet Payment
  memo: string | null;
  notes?: Note[]; // agent notes, append-only, display only
  secondOpinion?: SecondOpinion | "off" | null; // "off": SECOND_OPINION=off scripted run; null: no second opinion (timeout, failure, or a refused request)
  secondOpinionMs?: number | null; // wall time of the model call; null on refuse (no call)
  policyHash?: string; // sha256(canonical policy JSON)[:16] at decide time; missing on records from before it existed
  blobKey?: string | null; // "<Account>:<Sequence>" of the signed LoanSet (idempotency key)
  loanSetHash?: string; // sha256(signed LoanSet blob bytes), uppercase hex: the MemoData of the Ledger approval
  approvalTxHash?: string | null; // testnet Payment the Ledger signed (decidedBy "ledger")
  approvedBy?: string; // "operator" (token-only approve) or the approver account whose Ledger Payment approved
  approvedAt?: number; // unix seconds the desk accepted the approve
};

// GET /health. approverAccount set = approve needs a Ledger-signed testnet Payment (wallet POST /v1/lend/approve).
export type Health = { ok: boolean; network: string; broker: string; ledgerIndex: number; approverAccount?: string | null };

// Agent 2: the model can only tighten. status/reason carry its effect; decision stays the policy's.
export type SecondOpinion = { recommendation: "agree" | "hold" | "deny"; memo: string; flags: string[] };

// POST /v1/loan-requests/{id}/notes. Never a decision field.
export type Note = { from: string; text: string; ts: number };

export type LoanStatus = "active" | "impaired" | "defaulted" | "paid";

// The LoanManage(default) of a loan and its cover hit, stored by the desk (data/defaults.json).
export type LoanDefault = {
  hash: string;
  engineResult: string;
  coverBeforeDrops: string;
  coverAfterDrops: string;
  coverAbsorbedDrops: string;
  // From the LoanManage(default) meta: Vault AssetsTotal drop (what depositors absorbed) and the Loan's
  // principal before the default. Cover + vault loss = default amount. null: meta not read.
  vaultLossDrops?: string | null;
  defaultAmountDrops?: string | null;
  ts: number;
};

// POST /v1/broker/cover (LoanBrokerCoverDeposit by the broker key in the desk).
export type CoverTopUp = {
  hash: string | null;
  engineResult: string | null;
  coverBeforeDrops: string;
  coverAfterDrops: string | null;
};

// POST /v1/loans/{loanId}/sweeps (INTERFACES §9): an auto-repay LoanPay from x402 income, verified on devnet.
export type Sweep = {
  loanId: string;
  borrower: string;
  loanPayHash: string;
  incomeHash: string;
  incomeDrops: string;
  payer: string;
  drops: string;
  engineResult: string;
  status: string; // "repaid" | "failed: <engine code>"
  ledgerIndex: number | null;
  at: number;
  verifiedAt: number;
};

export type Loan = {
  loanId: string;
  borrower: string;
  principalDrops: string;
  totalOutstandingDrops: string;
  periodicPaymentDrops: string;
  interestRate: number;
  paymentInterval: number;
  gracePeriod: number;
  nextPaymentDue: number;
  paymentRemaining: number;
  startDate: number;
  status: LoanStatus;
  requestId: string | null;
  default?: LoanDefault | null; // null: not a default, or the desk could not look it up this poll
  sweeps?: Sweep[]; // auto-repay installments, oldest first (missing on desks from before §9)
};

export type VaultPhase = "subscription" | "lending" | "redemption";

export type Vault = {
  vaultId: string;
  loanBrokerId: string;
  shareMptId: string;
  assetsTotalDrops: string;
  assetsAvailableDrops: string;
  loansOutstandingDrops: string;
  debtTotalDrops: string;
  lossUnrealizedDrops: string;
  coverDrops: string;
  sharesTotal: string;
  utilizationPct: number;
  coverRatioPct: number;
  subscriptionDate: number;
  redemptionDate: number;
  ledgerIndex: number;
  // Close-ended vault phase (desk adds these; computed client-side if absent).
  phase?: VaultPhase;
  secondsToLending?: number;
  accounts?: Record<string, string>;
  setupTx?: Record<string, string>;
  policy?: Policy;
};

// GET/PUT /v1/policy (INTERFACES §5). Every cap, threshold and limit the UI shows comes from here.
export type Policy = {
  maxAutoPrincipalDrops: string;
  maxPrincipalDrops: string;
  minScoreAuto: number;
  minScore: number;
  maxUtilizationPct: number;
  minCoverRatioPct: number;
  termSecondsMin: number;
  termSecondsMax: number;
  interestRateBps: number;
  holdTimeoutSeconds: number;
  maxPendingDrops?: string; // cap on held + in-flight principal; "0" = no cap
};
