// One testnet WebSocket that recovers. After the Mac sleeps, xrpl.js keeps a half-dead socket:
// requests time out and every later connect() throws "Websocket connection never cleaned up".
// So a broken Client is dropped and a fresh one opened, reads retry once, and a watchdog
// reconnects after a sleep (wall-clock jump) or a failed ping.
import { Client } from "xrpl";

const REQUEST_TIMEOUT_MS = 10_000;

/** Errors that mean the socket is dead or stuck, not that rippled answered. */
export function isConnectionError(e: unknown): boolean {
  const { name = "", message = "" } = (e ?? {}) as { name?: string; message?: string };
  return (
    /^(ConnectionError|NotConnectedError|DisconnectedError|TimeoutError)$/.test(name) ||
    /never cleaned up|not connected|disconnected|timeout for request|websocket/i.test(message)
  );
}

export class XrplConnection {
  private client: Client | null = null;
  private opening: Promise<Client> | null = null;

  constructor(
    private readonly url: string,
    private readonly log: (msg: string) => void = console.log,
    private readonly factory: (url: string) => Client = (url) => new Client(url, { timeout: REQUEST_TIMEOUT_MS }),
  ) {}

  /** A connected client; opens a fresh one if the current one is gone. */
  get(): Promise<Client> {
    if (this.client?.isConnected()) return Promise.resolve(this.client);
    this.opening ??= this.open().finally(() => (this.opening = null));
    return this.opening;
  }

  private async open(): Promise<Client> {
    this.drop();
    const client = this.factory(this.url);
    // An unhandled "error" event would crash the process.
    client.on("error", (...args: unknown[]) => this.log(`xrpl socket error: ${args.map(String).join(" ")}`));
    await client.connect();
    this.client = client;
    return client;
  }

  /** Forgets the current client without waiting: a stale socket may never finish closing. */
  drop(reason?: string): void {
    const old = this.client;
    this.client = null;
    if (!old) return;
    if (reason) this.log(`xrpl reconnect: ${reason}`);
    void old.disconnect().catch(() => {});
  }

  /** For reads only: on a connection error, reconnect and retry once. Never wrap a submit. */
  async read<T>(fn: (client: Client) => Promise<T>): Promise<T> {
    try {
      return await fn(await this.get());
    } catch (e) {
      if (!isConnectionError(e)) throw e;
      this.drop(`${(e as Error).message.slice(0, 120)}; retrying once`);
      return fn(await this.get());
    }
  }

  /** Every 5 s: reconnect after a sleep (clock jump); every 30 s: ping, reconnect on failure. */
  watchdog(tickMs = 5_000, pingEveryTicks = 6): NodeJS.Timeout {
    let last = Date.now();
    let ticks = 0;
    const timer = setInterval(() => {
      const now = Date.now();
      const gap = now - last;
      last = now;
      if (gap > tickMs * 3) {
        this.drop(`wake detected (process paused ~${Math.round(gap / 1000)} s)`);
        return;
      }
      if (++ticks % pingEveryTicks !== 0 || !this.client) return;
      const client = this.client;
      client.request({ command: "ping" }).catch((e: unknown) => {
        if (this.client === client) this.drop(`watchdog ping failed: ${(e as Error).message.slice(0, 120)}`);
      });
    }, tickMs);
    timer.unref();
    return timer;
  }

  async close(): Promise<void> {
    const old = this.client;
    this.client = null;
    await old?.disconnect().catch(() => {});
  }
}
