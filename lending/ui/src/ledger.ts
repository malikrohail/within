// Read-only devnet lookups the desk API does not carry (validated ledger of a tx, the LoanManage default
// and its cover hit). Devnet JSON-RPC sends no CORS headers, so the browser uses the WebSocket API.
const WS_URL = "wss://s.devnet.rippletest.net:51233/";

function ws<T>(req: Record<string, unknown>, timeoutMs = 8000): Promise<T> {
  return new Promise((resolve, reject) => {
    let sock: WebSocket;
    try {
      sock = new WebSocket(WS_URL);
    } catch (e) {
      reject(e);
      return;
    }
    const timer = setTimeout(() => {
      sock.close();
      reject(new Error("devnet timeout"));
    }, timeoutMs);
    sock.onopen = () => sock.send(JSON.stringify({ id: 1, ...req }));
    sock.onerror = () => {
      clearTimeout(timer);
      reject(new Error("devnet unreachable"));
    };
    sock.onmessage = (m) => {
      clearTimeout(timer);
      sock.close();
      const d = JSON.parse(String(m.data));
      if (d.status === "success") resolve(d.result as T);
      else reject(new Error(d.error ?? "devnet error"));
    };
  });
}

/** Validated ledger index of a transaction, or null. */
export async function txLedgerIndex(hash: string): Promise<number | null> {
  try {
    const r = await ws<{ ledger_index?: number; validated?: boolean }>({ command: "tx", transaction: hash });
    return r.validated && typeof r.ledger_index === "number" ? r.ledger_index : null;
  } catch {
    return null;
  }
}

export type DefaultInfo = { hash: string; coverAbsorbedDrops: string | null; vaultLossDrops?: string | null };

type Node = { ModifiedNode?: { LedgerEntryType: string; PreviousFields?: Record<string, string>; FinalFields?: Record<string, string> } };
type AccountTx = { transactions: { tx?: Record<string, unknown> & { hash?: string }; tx_json?: Record<string, unknown>; hash?: string; meta: { AffectedNodes: Node[] } }[] };

const TF_LOAN_DEFAULT = 0x10000;

/** The broker's LoanManage(default) for each loan id, with CoverAvailable before minus after. */
export async function findDefaults(broker: string, loanIds: string[]): Promise<Record<string, DefaultInfo>> {
  const r = await ws<AccountTx>({ command: "account_tx", account: broker, limit: 400 });
  const out: Record<string, DefaultInfo> = {};
  for (const t of r.transactions) {
    const tx = (t.tx_json ?? t.tx ?? {}) as Record<string, unknown>;
    const loanId = tx.LoanID as string | undefined;
    if (tx.TransactionType !== "LoanManage" || !loanId || !loanIds.includes(loanId)) continue;
    if (!((Number(tx.Flags) & TF_LOAN_DEFAULT) !== 0)) continue;
    const hash = (t.hash ?? (tx.hash as string)) as string;
    const lb = t.meta.AffectedNodes.find((n) => n.ModifiedNode?.LedgerEntryType === "LoanBroker")?.ModifiedNode;
    if (!lb) continue;
    // CoverAvailable is soeDEFAULT: rippled omits it at 0, so a missing FinalFields value is a drained cover.
    const after = lb.FinalFields?.CoverAvailable ?? "0";
    // PreviousFields omits CoverAvailable when the cover did not move.
    const before = lb.PreviousFields?.CoverAvailable ?? after;
    // Depositors' share: the Vault's AssetsTotal drop (absent from PreviousFields = unchanged).
    const v = t.meta.AffectedNodes.find((n) => n.ModifiedNode?.LedgerEntryType === "Vault")?.ModifiedNode;
    const vAfter = v?.FinalFields?.AssetsTotal ?? "0";
    const vaultLossDrops = v ? String(BigInt(v.PreviousFields?.AssetsTotal ?? vAfter) - BigInt(vAfter)) : null;
    out[loanId] = { hash, coverAbsorbedDrops: String(BigInt(before) - BigInt(after)), vaultLossDrops };
  }
  return out;
}
