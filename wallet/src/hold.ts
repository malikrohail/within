import { hashes, encode, type SubmittableTransaction } from "xrpl";
import { DeviceError, type DeviceSignAction, type DeviceSigner } from "./device.js";
import type { SignedTx } from "./types.js";

export type HoldOutcome =
  | { kind: "approved"; signed: SignedTx }
  | { kind: "denied" }
  | { kind: "expired" }
  | { kind: "unavailable"; detail: string };

/** What the hold queue needs from the emulator driver (Speculos in the demo). */
export interface Tapper {
  approve(log?: (msg: string) => void, isDone?: () => boolean): Promise<void>;
  reject(log?: (msg: string) => void): Promise<boolean>;
  waitForReview(timeoutMs: number): Promise<boolean>;
}

type Entry = {
  id: string;
  tx: SubmittableTransaction;
  done: boolean;
  tapping: boolean;
  action: DeviceSignAction | null;
  cleanup: Promise<void> | null;
  timer: NodeJS.Timeout;
  resolve: (o: HoldOutcome) => void;
};

/** Device signs one request at a time; later holds queue behind the current one. */
export class HoldQueue {
  private entries = new Map<string, Entry>();
  private chain: Promise<void> = Promise.resolve();

  constructor(
    private readonly device: DeviceSigner,
    private readonly tapper: Tapper,
    private readonly log: (msg: string) => void = console.log,
  ) {}

  pendingCount(): number {
    return [...this.entries.values()].filter((e) => !e.done).length;
  }

  isPending(id: string): boolean {
    return this.entries.get(id)?.done === false;
  }

  /** Resolves when the device approves, the user denies, the device fails, or timeoutMs passes. */
  create(id: string, tx: SubmittableTransaction, timeoutMs: number): Promise<HoldOutcome> {
    return new Promise((resolve) => {
      const entry: Entry = {
        id, tx, resolve, done: false, tapping: false, action: null, cleanup: null,
        timer: setTimeout(() => this.finish(entry, { kind: "expired" }), timeoutMs),
      };
      this.entries.set(id, entry);
      this.chain = this.chain.then(() => this.run(entry));
    });
  }

  private async run(entry: Entry): Promise<void> {
    if (entry.done) return;
    entry.action = this.device.sign(encode(entry.tx));
    let outcome: HoldOutcome;
    try {
      const der = await entry.action.result;
      const blob = encode({ ...entry.tx, TxnSignature: Buffer.from(der).toString("hex").toUpperCase() });
      outcome = { kind: "approved", signed: { blob, hash: hashes.hashSignedTx(blob) } };
    } catch (e) {
      const err = e as DeviceError;
      outcome = err.code === "rejected_on_device" ? { kind: "denied" } : { kind: "unavailable", detail: err.message };
    }
    this.finish(entry, outcome);
    // Do not start the next device action until this one has left the screen.
    if (entry.cleanup) await entry.cleanup;
  }

  private finish(entry: Entry, outcome: HoldOutcome): void {
    if (entry.done) return;
    entry.done = true;
    clearTimeout(entry.timer);
    if (outcome.kind !== "approved" && entry.action) entry.cleanup = this.clearDevice(entry.action);
    entry.resolve(outcome);
  }

  /** Reject the review if it is on screen (so the pending APDU returns), then cancel the DMK action. */
  private async clearDevice(action: DeviceSignAction): Promise<void> {
    try {
      const onScreen = await this.tapper.waitForReview(3000);
      this.log(`device cleanup: review on screen=${onScreen}`);
      if (onScreen) {
        const gone = await this.tapper.reject((msg) => this.log(`device cleanup: ${msg}`));
        if (!gone) this.log("device cleanup: review could not be cleared; the next hold will clear it at boot or reject again");
      }
    } catch (e) {
      this.log(`device reject tap failed: ${(e as Error).message}`);
    }
    action.cancel();
    await action.result.catch(() => {});
  }

  /** Demo helper: drive the emulator once this request's review is on screen. False if not pending. */
  tap(id: string): boolean {
    const entry = this.entries.get(id);
    if (!entry || entry.done) return false;
    if (entry.tapping) return true;
    entry.tapping = true;
    this.log(`device-tap id=${id}: requested (device action started=${entry.action !== null})`);
    void (async () => {
      while (!entry.done && !entry.action) await new Promise((r) => setTimeout(r, 250));
      if (entry.done) return;
      if (!(await this.tapper.waitForReview(15000)) || entry.done) return this.log(`device-tap id=${id}: no review on screen`);
      this.log(`device-tap id=${id}: review seen`);
      await this.tapper.approve((msg) => this.log(`device-tap id=${id}: ${msg}`), () => entry.done);
    })()
      .catch((e) => this.log(`device-tap id=${id} failed: ${(e as Error).message}`))
      .finally(() => (entry.tapping = false));
    return true;
  }

  /** Deny a pending request: resolves its /v1/pay with denied. False if not pending. */
  deny(id: string): boolean {
    const entry = this.entries.get(id);
    if (!entry || entry.done) return false;
    this.finish(entry, { kind: "denied" });
    return true;
  }
}
