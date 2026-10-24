import { appendFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";
import type { RequestRow } from "./types.js";

/**
 * Append-only JSON lines. A resolved held request appends a superseding line with the
 * same id; the in-memory index keeps the last line per id, in first-seen order.
 */
export class Audit {
  private rows = new Map<string, RequestRow>();

  constructor(private readonly path: string) {
    mkdirSync(dirname(path), { recursive: true });
    if (existsSync(path)) {
      for (const line of readFileSync(path, "utf8").split("\n")) {
        if (!line.trim()) continue;
        const row = JSON.parse(line) as RequestRow;
        this.rows.set(row.id, row);
      }
    }
    // A held row left by a previous process can never resolve: its /v1/pay caller is gone.
    for (const row of this.rows.values()) {
      if (row.status === "held") this.put({ ...row, status: "expired", reason: "hold_timeout" });
    }
  }

  put(row: RequestRow): void {
    this.rows.set(row.id, row);
    appendFileSync(this.path, JSON.stringify(row) + "\n");
  }

  get(id: string): RequestRow | undefined {
    return this.rows.get(id);
  }

  update(id: string, patch: Partial<RequestRow>): RequestRow {
    const row = { ...this.rows.get(id)!, ...patch };
    this.put(row);
    return row;
  }

  /** Newest first. */
  list(limit = 200): RequestRow[] {
    return [...this.rows.values()].reverse().slice(0, limit);
  }

  /** Sum of auto|approved amounts since 00:00 local time. */
  spentToday(now = new Date()): bigint {
    const midnight = new Date(now);
    midnight.setHours(0, 0, 0, 0);
    let sum = 0n;
    for (const row of this.rows.values()) {
      if ((row.status === "auto" || row.status === "approved") && new Date(row.ts) >= midnight) {
        sum += BigInt(row.amountDrops);
      }
    }
    return sum;
  }
}
