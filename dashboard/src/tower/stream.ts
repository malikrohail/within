// One rippled WebSocket per network: seeds recent history with account_tx, then `subscribe` to the
// known accounts for live validated transactions. Reconnects (next URL) when the socket drops.
import { WS_URLS, type Network } from "./flows";

export type LedgerTx = { tx: Record<string, unknown>; hash: string; date?: number; result?: string };

type Pending = (result: Record<string, unknown>) => void;

export class LedgerStream {
  private ws: WebSocket | null = null;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private urlIndex = 0;
  private closed = false;
  private retry: ReturnType<typeof setTimeout> | null = null;

  constructor(
    readonly network: Network,
    private readonly accounts: string[],
    private readonly onTx: (t: LedgerTx, live: boolean) => void,
    private readonly onState: (state: string) => void = () => {},
  ) {}

  start(): void {
    const url = WS_URLS[this.network][this.urlIndex % WS_URLS[this.network].length];
    const ws = new WebSocket(url);
    this.ws = ws;
    this.onState(`connecting ${new URL(url).host}`);
    ws.onopen = async () => {
      this.onState(`live ${new URL(url).host}`);
      // Subscribe first and seed every account's recent history in parallel, so the graph fills in one round trip.
      this.request({ command: "subscribe", accounts: this.accounts });
      const pages = await Promise.all(this.accounts.map((account) => this.request({ command: "account_tx", account, limit: 15 })));
      for (const r of pages) for (const item of ((r.transactions as unknown[]) ?? []).slice().reverse()) this.emit(item as Record<string, unknown>, false);
    };
    ws.onmessage = (m) => {
      const msg = JSON.parse(String(m.data)) as Record<string, unknown>;
      if (typeof msg.id === "number" && this.pending.has(msg.id)) {
        this.pending.get(msg.id)!((msg.result as Record<string, unknown>) ?? {});
        this.pending.delete(msg.id);
      } else if (msg.type === "transaction" && msg.validated) this.emit(msg, true);
    };
    ws.onclose = () => {
      for (const resolve of this.pending.values()) resolve({});
      this.pending.clear();
      if (this.closed) return;
      this.onState("reconnecting");
      this.urlIndex++;
      this.retry = setTimeout(() => this.start(), 3000);
    };
    ws.onerror = () => ws.close();
  }

  /** account_tx rows and stream messages: API v1 uses `transaction`/`tx`, v2 `tx_json`. Only tesSUCCESS counts. */
  private emit(item: Record<string, unknown>, live: boolean): void {
    const tx = (item.tx_json ?? item.transaction ?? item.tx) as Record<string, unknown> | undefined;
    if (!tx) return;
    const meta = item.meta as { TransactionResult?: string } | undefined;
    if (meta?.TransactionResult !== "tesSUCCESS") return;
    const hash = (item.hash ?? tx.hash) as string;
    const date = (tx.date ?? item.date) as number | undefined;
    this.onTx({ tx, hash, date, result: meta.TransactionResult }, live);
  }

  request(body: Record<string, unknown>): Promise<Record<string, unknown>> {
    const ws = this.ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) return Promise.resolve({});
    const id = this.nextId++;
    return new Promise((resolve) => {
      this.pending.set(id, resolve);
      ws.send(JSON.stringify({ id, ...body }));
    });
  }

  stop(): void {
    this.closed = true;
    if (this.retry) clearTimeout(this.retry);
    this.ws?.close();
  }
}
